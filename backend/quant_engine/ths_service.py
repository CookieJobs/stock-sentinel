"""同花顺财务指标 enrichment 服务

- 财务指标接口为单股调用（thscode + 报告期）→ 全市场逐股拉太重，
  设计为「监控列表 + 指定列表」按需拉取，结果缓存到 ths_indicators 表
  （按报告期判断新鲜度：报告期变了或超过 7 天则重拉）。
- 接入 refresh_universe：universe df 落库前，给监控股票行附加
  roe/roa/gross_margin/net_margin/debt_ratio/revenue_yoy/profit_yoy 列，
  从而成长/质量因子对监控股票有真实值参与截面排名。
"""
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from .db import get_quant_db
from .data_source.ths_source import THSApiClient, financial_indicators_latest, latest_report

logger = logging.getLogger(__name__)

# 指标列（与 INDICATOR_MAP 值一致，也是 FACTOR_REGISTRY 键）
INDICATOR_COLS = ["roe", "roa", "gross_margin", "net_margin",
                  "debt_ratio", "revenue_yoy", "profit_yoy"]

# 单次刷新最多新拉多少只（保护配额；监控列表默认 71 只，留余量）
MAX_FRESH_PER_REFRESH = 100


def get_monitored_tickers() -> List[str]:
    """v0.2.0 监控列表（stocks 表）"""
    from database import get_db
    db = get_db()
    try:
        rows = db.execute("SELECT ticker FROM stocks ORDER BY ticker").fetchall()
        return [r["ticker"] for r in rows]
    finally:
        db.close()


def get_cached_indicators(tickers: List[str]) -> Dict[str, dict]:
    """读缓存：{ticker: {col: value}}"""
    if not tickers:
        return {}
    ph = ",".join("?" * len(tickers))
    db = get_quant_db()
    try:
        rows = db.execute(
            f"SELECT ticker, report, fetched_at, {', '.join(INDICATOR_COLS)} "
            f"FROM ths_indicators WHERE ticker IN ({ph})",
            tickers,
        ).fetchall()
    finally:
        db.close()
    out: Dict[str, dict] = {}
    for r in rows:
        d = {c: r[c] for c in INDICATOR_COLS}
        out[r["ticker"]] = {"report": r["report"], "fetched_at": r["fetched_at"], **d}
    return out


def _cache_indicators(ticker: str, report: str, values: Dict[str, Optional[float]]) -> None:
    db = get_quant_db()
    try:
        db.execute(
            """INSERT OR REPLACE INTO ths_indicators
               (ticker, report, roe, roa, gross_margin, net_margin, debt_ratio,
                revenue_yoy, profit_yoy, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, report,
             values.get("roe"), values.get("roa"), values.get("gross_margin"),
             values.get("net_margin"), values.get("debt_ratio"),
             values.get("revenue_yoy"), values.get("profit_yoy"),
             datetime.now().isoformat()),
        )
        db.commit()
    finally:
        db.close()


def refresh_indicators(tickers: List[str]) -> int:
    """拉取并缓存指定列表的财务指标（报告期未变的缓存直接复用）；返回新拉数量"""
    if not os.environ.get("THS_API_KEY"):
        logger.warning("THS_API_KEY 未配置，跳过财务指标刷新")
        return 0
    cached = get_cached_indicators(tickers)
    current_report = latest_report(datetime.now().year, datetime.now().month)

    client = THSApiClient()
    fetched = 0
    for ticker in tickers:
        info = cached.get(ticker)
        if info and info.get("report") == current_report:
            continue  # 报告期未变，直接用缓存（季度才更新一次）
        try:
            from .data_source.ths_source import ticker_to_thscode
            thscode = ticker_to_thscode(ticker)
            values = financial_indicators_latest(client, thscode,
                                                 datetime.now().year, datetime.now().month)
        except Exception as e:
            logger.warning("THS indicators %s failed: %s", ticker, e)
            continue
        _cache_indicators(ticker, current_report, values)
        fetched += 1
        if fetched >= MAX_FRESH_PER_REFRESH:
            logger.warning("THS indicator refresh reached cap %d", MAX_FRESH_PER_REFRESH)
            break
    if fetched:
        logger.info("THS indicators refreshed %d stocks", fetched)
    return fetched


def enrich_universe_df(df: pd.DataFrame) -> pd.DataFrame:
    """给 universe df 附加监控股票的财务指标列（其余行 NaN，不参与排名）"""
    for col in INDICATOR_COLS:
        if col not in df.columns:
            df[col] = float("nan")
    monitored = [t for t in get_monitored_tickers() if t in set(df["ticker"])]
    if not monitored:
        return df
    refresh_indicators(monitored)
    cached = get_cached_indicators(monitored)
    idx_map = {row: i for i, row in enumerate(df["ticker"])}
    for ticker, info in cached.items():
        i = idx_map.get(ticker)
        if i is None:
            continue
        for col in INDICATOR_COLS:
            df.at[i, col] = info.get(col)
    return df


# ── 异动归因（special-data / anomaly-analysis） ──────────────

ANOMALY_TAGS = "LIMIT_UP,LIMIT_DOWN,SHARP_RISE,SHARP_FALL,RAPID_RALLY,RAPID_DECLINE"
_TAG_NAME_MAP = {
    "涨停": "LIMIT_UP", "跌停": "LIMIT_DOWN",
    "大涨": "SHARP_RISE", "大跌": "SHARP_FALL",
    "快速拉升": "RAPID_RALLY", "快速下挫": "RAPID_DECLINE",
}


def fetch_anomalies(trade_date: Optional[str] = None) -> int:
    """拉当日全市场个股异动原因并入库（交易日才有数据，周末为空属正常）"""
    if not os.environ.get("THS_API_KEY"):
        return 0
    client = THSApiClient()
    try:
        data = client._get("/api/a-share/special-data/anomaly-analysis-list",
                           {"tag_codes": ANOMALY_TAGS})
    except ValueError as e:
        logger.warning("THS anomaly fetch failed: %s", e)
        return 0
    items = data.get("item") or []
    if not items:
        return 0
    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().isoformat()
    db = get_quant_db()
    try:
        db.executemany(
            """INSERT OR REPLACE INTO quant_anomalies
               (trade_date, ticker, name, tag, reason, keywords, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [(
                trade_date,
                str(it.get("thscode", "")).split(".")[0],
                it.get("stock_name"),
                _TAG_NAME_MAP.get(it.get("tag_name", ""), it.get("tag_name", "")),
                it.get("analysis_content"),
                __import__("json").dumps(it.get("keyword_list") or [], ensure_ascii=False),
                now,
            ) for it in items],
        )
        db.commit()
        logger.info("THS anomalies stored: %d", len(items))
        return len(items)
    finally:
        db.close()


def get_anomalies(trade_date: Optional[str] = None, tag: Optional[str] = None,
                  tickers: Optional[List[str]] = None, limit: int = 100) -> list:
    """查询异动记录（按日期/标签/股票过滤）"""
    sql = "SELECT trade_date, ticker, name, tag, reason, keywords FROM quant_anomalies WHERE 1=1"
    params: list = []
    if trade_date:
        sql += " AND trade_date = ?"
        params.append(trade_date)
    if tag:
        sql += " AND tag = ?"
        params.append(tag)
    if tickers:
        sql += f" AND ticker IN ({','.join('?' * len(tickers))})"
        params.extend(tickers)
    sql += " ORDER BY trade_date DESC, ticker LIMIT ?"
    params.append(limit)
    db = get_quant_db()
    try:
        return [dict(r) for r in db.execute(sql, params).fetchall()]
    finally:
        db.close()
