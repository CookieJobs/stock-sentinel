"""因子服务 — 选股器核心

- 拉全 A 股数据（按数据源优先级） → 入库 factor_values
- 多条件筛选 + 排名 → 返回 Top N
- 5 大类因子：估值/成长/质量/动量/波动
"""
from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from .db import get_quant_db
from .factors import FACTOR_REGISTRY, cross_sectional_rank
from .data_source.factor_source import get_factor_source, MockFactorSource, AkShareFactorSource, TushareFactorSource

logger = logging.getLogger(__name__)


# ── 入库 ──────────────────────────────────────────────────────

def refresh_universe() -> int:
    """拉取全 A 股数据并写入 factor_values 表

    Returns: 入库行数
    """
    # 按数据源优先级逐个尝试（任一成功即用）
    from .data_source.factor_source import SOURCES as SRC_LIST
    df = None
    actual_src = None
    for src_cls in SRC_LIST:
        try:
            if getattr(src_cls, "required_env", None) and not os.environ.get(src_cls.required_env):
                continue
            src = src_cls()
            df = src.get_universe()
            # 只有含因子列的 df 才算"该源可用"：Tushare 限流回退缓存时返回的
            # 空壳 universe（无 PE/PB 等）不算成功，继续降级到下一个源
            factor_cols = [c for c in FACTOR_REGISTRY if df is not None and c in df.columns]
            if df is not None and not df.empty and factor_cols:
                actual_src = src
                break
            logger.warning("Source %s returned %s rows without factor columns, trying next",
                           src.name if src else src_cls.__name__,
                           len(df) if df is not None else 0)
        except Exception as e:
            logger.warning("Source %s failed: %s", src_cls.__name__, e)
            continue

    if df is None or df.empty:
        logger.warning("All factor sources returned empty data")
        return 0
    logger.info("Loaded universe from %s: %d rows", actual_src.name, len(df))

    # 同花顺财务指标 enrichment：给监控股票的 df 行附加 roe/毛利率/增速等列
    if os.environ.get("THS_API_KEY"):
        try:
            from . import ths_service
            df = ths_service.enrich_universe_df(df)
        except Exception as e:
            logger.warning("THS indicator enrichment failed: %s", e)

    today = datetime.now().strftime("%Y-%m-%d")

    # 计算各因子的截面排名
    rank_records = []
    for factor_name, meta in FACTOR_REGISTRY.items():
        if factor_name not in df.columns:
            continue
        col = df[factor_name].astype(float)
        ascending = meta["direction"] == "asc"
        ranks = col.rank(method="min", ascending=ascending, na_option="bottom")
        for ticker, val, rank in zip(df["ticker"], col, ranks):
            if pd.isna(val):
                continue
            rank_records.append((ticker, today, factor_name, float(val), int(rank)))

    db = get_quant_db()
    try:
        cur = db.cursor()
        # 清当日旧数据
        cur.execute("DELETE FROM factor_values WHERE trade_date = ?", (today,))
        # 批量插入
        cur.executemany(
            """INSERT OR REPLACE INTO factor_values
               (ticker, trade_date, factor_name, factor_value, factor_rank)
               VALUES (?, ?, ?, ?, ?)""",
            rank_records,
        )

        # 同时把 universe 基础信息存到 daily_metrics（无日期历史，先存当前）
        cur.execute("DELETE FROM daily_metrics WHERE trade_date = ?", (today,))
        metric_records = []
        for _, r in df.iterrows():
            metric_records.append((
                r["ticker"], today,
                r.get("name"), r.get("industry"),
                r.get("pe_ttm"), r.get("pb"), r.get("ps_ttm"), None,
                r.get("market_cap"), r.get("turnover_rate"),
                r.get("roe"), r.get("roa"),
                r.get("revenue_yoy"), r.get("profit_yoy"),
                r.get("gross_margin"), r.get("net_margin"),
                r.get("debt_ratio"), None,
            ))
        cur.executemany(
            """INSERT OR REPLACE INTO daily_metrics
               (ticker, trade_date, name, industry,
                pe_ttm, pb, ps_ttm, peg,
                market_cap, turnover_rate, roe, roa,
                revenue_yoy, profit_yoy, gross_margin, net_margin,
                debt_ratio, free_cash_flow)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            metric_records,
        )
        db.commit()
        logger.info("Inserted %d factor_values and %d daily_metrics rows",
                    len(rank_records), len(metric_records))
        return len(rank_records)
    finally:
        db.close()


# ── 选股 ──────────────────────────────────────────────────────

def screen(
    *,
    filters: list[dict] = None,        # [{"factor": "pe_ttm", "min": 0, "max": 30}, ...]
    rank_by: Optional[str] = None,     # 排名因子
    top_n: int = 20,
    industries: Optional[list[str]] = None,  # 行业筛选
    markets: Optional[list[str]] = None,       # 市场筛选
    exclude_st: bool = True,
) -> dict:
    """多条件选股

    Args:
        filters: 多条件筛选，每项 {factor, min, max, op}
        rank_by: 排名因子（FACTOR_REGISTRY 中）
        top_n: 返回前 N
        industries: 行业白名单（None = 全部）
        markets: 市场白名单（None = 全部）
    """
    filters = filters or []

    # 1. 从 daily_metrics 拉最新一天的数据
    db = get_quant_db()
    try:
        # 取最新日期
        row = db.execute("SELECT MAX(trade_date) AS d FROM daily_metrics").fetchone()
        if not row or not row["d"]:
            return {"error": "请先刷新因子库 (POST /api/quant/factors/refresh)", "results": []}
        latest_date = row["d"]
        rows = db.execute(
            "SELECT * FROM daily_metrics WHERE trade_date = ?",
            (latest_date,),
        ).fetchall()
    finally:
        db.close()

    if not rows:
        return {"error": "daily_metrics 表为空，请先刷新", "results": []}

    df = pd.DataFrame([dict(r) for r in rows])

    # 2. 行业筛选（daily_metrics.industry 列已存；BaoStock 提供申万行业）
    if industries:
        df = df[df["industry"].isin(industries)]

    # 3. 市场筛选
    if markets:
        df = df[df["market"].isin(markets)] if "market" in df.columns else df

    # 4. ST 排除（名字含 ST）
    if exclude_st and "name" in df.columns:
        df = df[~df["name"].astype(str).str.contains("ST|\\*ST", na=False, regex=True)]

    # 5. 多条件筛选
    for f in filters:
        factor = f.get("factor")
        if not factor or factor not in df.columns:
            continue
        col = pd.to_numeric(df[factor], errors="coerce")
        if "min" in f and f["min"] is not None:
            df = df[col >= float(f["min"])]
            col = col[df.index]
        if "max" in f and f["max"] is not None:
            df = df[col <= float(f["max"])]
            col = col[df.index]

    if df.empty:
        return {"trade_date": str(latest_date), "total_candidates": 0, "results": []}

    # 4. 排名
    if rank_by and rank_by in df.columns:
        meta = FACTOR_REGISTRY.get(rank_by, {})
        ascending = meta.get("direction") == "desc"  # 同样：ascending=False 让大值 rank 1
        col = pd.to_numeric(df[rank_by], errors="coerce")
        df = df.assign(_rank=col.rank(method="min", ascending=ascending, na_option="bottom"))
        df = df.sort_values("_rank")
    else:
        df["_rank"] = range(1, len(df) + 1)

    df = df.head(top_n)

    # 6. 格式化输出
    display_cols = ["ticker", "trade_date", "pe_ttm", "pb", "ps_ttm", "market_cap",
                    "turnover_rate", "roe", "gross_margin", "_rank"]
    result = []
    for _, r in df.iterrows():
        result.append({
            "ticker": r["ticker"],
            "trade_date": str(r["trade_date"]),
            "name": r.get("name", ""),
            "industry": r.get("industry", ""),
            "market": r.get("market", "CN"),
            "pe_ttm": _safe_float(r.get("pe_ttm")),
            "pb": _safe_float(r.get("pb")),
            "ps_ttm": _safe_float(r.get("ps_ttm")),
            "market_cap": _safe_float(r.get("market_cap")),
            "turnover_rate": _safe_float(r.get("turnover_rate")),
            "roe": _safe_float(r.get("roe")),
            "gross_margin": _safe_float(r.get("gross_margin")),
            "rank": int(r["_rank"]) if not pd.isna(r["_rank"]) else None,
        })

    return {
        "trade_date": str(latest_date),
        "total_candidates": len(df),
        "results": result,
    }


def _safe_float(v):
    if v is None or (isinstance(v, float) and v != v):
        return None
    try:
        return round(float(v), 4)
    except (ValueError, TypeError):
        return None


def list_factors_meta() -> list[dict]:
    """列出所有因子元信息（前端 UI 用）"""
    from .factors import list_factors
    return list_factors()


def get_universe_stats() -> dict:
    """当前 universe 统计"""
    db = get_quant_db()
    try:
        total = db.execute("SELECT COUNT(DISTINCT ticker) AS c FROM daily_metrics").fetchone()["c"]
        latest = db.execute("SELECT MAX(trade_date) AS d FROM daily_metrics").fetchone()["d"]
        factor_count = db.execute("SELECT COUNT(DISTINCT factor_name) AS c FROM factor_values").fetchone()["c"]
    finally:
        db.close()
    return {
        "universe_size": total,
        "latest_date": str(latest) if latest else None,
        "factor_count": factor_count,
        "source": get_factor_source().name,
    }
