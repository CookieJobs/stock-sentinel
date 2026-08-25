"""股票搜索服务 — 按 代码/名称（中文/拼音）检索，返回 代码+名称+市场

主源：东方财富 suggest API（免 key，覆盖沪深港美）：
    https://searchapi.eastmoney.com/api/suggest/get?input=<q>&type=14&token=...
    - type=14 同时匹配 代码 / 中文名 / 拼音缩写
    - 返回项含 Code / Name / MktNum / SecurityType / TypeUS 等字段
降级源：本地库（东财不可达时兜底）：
    - v0.2.0 `stocks` 自选表（ticker/name）
    - 量化 `ts_universe_cache` / `daily_metrics`（name 列，A 股为主）

市场过滤规则（2026-08-24 对 suggest API 实测归纳，排除指数/债券/Notes/权证）：
    - CN：MktNum ∈ {0,1} 且 SecurityType ∈ {1,2,3,4}（沪深 A/B 股）
    - HK：MktNum = 116 且 SecurityType ∈ {6,19} 且 TypeUS = 3（正股；TypeUS=2 是债券）
    - US：MktNum ∈ {105,106,107} 且 TypeUS ∈ {1,2,3,4,5}（普通股/ADR/ETF；TypeUS=6 是 Notes）
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 东财前端公开常量（非密钥，suggest 接口固定使用）
_EM_SUGGEST_HOST = "searchapi.eastmoney.com"
_EM_SUGGEST_PATH = "/api/suggest/get"
_EM_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"

# MktNum → 市场
_MKTNUMS = {
    "CN": ("0", "1"),
    "HK": ("116",),
    "US": ("105", "106", "107"),
}

# SecurityType 白名单（CN A/B 股；排除指数 5、债券 16）
_CN_SEC_TYPES = {"1", "2", "3", "4"}
# HK 正股 SecurityType（6=港股老类型、19=新类型），叠加 TypeUS=3 判定
_HK_SEC_TYPES = {"6", "19"}
# US 可交易品种 TypeUS（1=普通股、3=ADR、5=ETF；排除 6=Notes/债券）
_US_TYPEUS = {"1", "2", "3", "4", "5"}


def classify_market(item: Dict[str, Any]) -> Optional[str]:
    """按 suggest 返回项的市场字段判定市场；非股票（指数/债券/Notes 等）返回 None"""
    mktnum = str(item.get("MktNum", ""))
    sectype = str(item.get("SecurityType", ""))
    typeus = str(item.get("TypeUS", ""))
    if mktnum in _MKTNUMS["CN"]:
        return "CN" if sectype in _CN_SEC_TYPES else None
    if mktnum in _MKTNUMS["HK"]:
        return "HK" if sectype in _HK_SEC_TYPES and typeus == "3" else None
    if mktnum in _MKTNUMS["US"]:
        return "US" if typeus in _US_TYPEUS else None
    return None


def _em_suggest(q: str, count: int) -> Optional[List[Dict[str, Any]]]:
    """调东财 suggest；失败/无数据返回 None

    注意：必须用 urllib 直连 — `requests`（含 data_fetcher._em_get）的 TLS 指纹会被
    东财 CDN 路由到一份 2023 年的陈旧 JSONP 缓存（passport 接口残留），拿不到行情数据；
    urllib/curl 的指纹正常（2026-08-24 实测）。
    """
    params = urllib.parse.urlencode(
        {"input": q, "type": 14, "token": _EM_TOKEN, "count": count}
    )
    last_err: Optional[Exception] = None
    for scheme in ("https", "http"):
        url = f"{scheme}://{_EM_SUGGEST_HOST}{_EM_SUGGEST_PATH}?{params}"
        try:
            with urllib.request.urlopen(url, timeout=6) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace"))
            data = payload.get("QuotationCodeTable", {}).get("Data") or []
            return list(data)
        except Exception as e:
            last_err = e
    logger.warning("EastMoney suggest failed for q=%r: %s", q, last_err)
    return None


def _local_search(q: str, limit: int) -> List[Dict[str, Any]]:
    """本地降级：自选表 + 量化名称表 LIKE 匹配（q 为空时全量取前 limit 条）"""
    results: List[Dict[str, Any]] = []
    like = f"%{q}%"

    def _add(ticker: str, name: str, market: str) -> None:
        if not ticker or not name:
            return
        results.append({"ticker": ticker, "name": name, "market": market, "source": "local"})

    # 1. v0.2.0 自选表（三市场）
    try:
        from database import get_db
        db = get_db()
        rows = db.execute(
            "SELECT ticker, name, market FROM stocks WHERE ticker LIKE ? OR name LIKE ? ORDER BY id LIMIT ?",
            (like, like, limit),
        ).fetchall()
        for r in rows:
            _add(str(r["ticker"]), str(r["name"] or ""), str(r["market"] or "").upper() or "CN")
    except Exception as e:
        logger.warning("local stocks search failed: %s", e)

    # 2. 量化名称表（A 股为主）
    try:
        from .db import get_quant_db
        qdb = get_quant_db()
        seen = {r["ticker"] for r in results}
        for table, cols in (("ts_universe_cache", "ticker, name"), ("daily_metrics", "ticker, name")):
            try:
                rows = qdb.execute(
                    f"SELECT {cols} FROM {table} WHERE name LIKE ? ORDER BY ticker LIMIT ?",
                    (like, limit),
                ).fetchall()
            except Exception:
                continue  # 表可能不存在（新库）
            for r in rows:
                ticker = str(r["ticker"])
                if ticker in seen:
                    continue
                seen.add(ticker)
                _add(ticker, str(r["name"] or ""), "CN")
    except Exception as e:
        logger.warning("quant local search failed: %s", e)

    return results[:limit]


def search_stocks(q: str, limit: int = 10, market: Optional[str] = None) -> List[Dict[str, Any]]:
    """搜索股票：东财 suggest 优先，本地降级；按 (market, ticker) 去重，市场过滤

    返回 [{ticker, name, market, source}]，source ∈ {eastmoney, local}
    """
    q = (q or "").strip()
    limit = max(1, min(int(limit), 20))
    market = (market or "").upper()
    if market not in ("CN", "HK", "US"):
        market = None

    merged: Dict[tuple, Dict[str, Any]] = {}
    items = _em_suggest(q, limit * 2)  # 多取一些，过滤后仍够数
    if items:
        for it in items:
            m = classify_market(it)
            if m is None or (market and m != market):
                continue
            ticker = str(it.get("Code", "")).strip().upper()
            name = str(it.get("Name", "")).strip()
            if not ticker or not name:
                continue
            merged[(m, ticker)] = {"ticker": ticker, "name": name, "market": m, "source": "eastmoney"}

    # 东财结果不足以覆盖 limit 时补本地（降级/扩充）
    if len(merged) < limit:
        for r in _local_search(q, limit * 2):
            if market and r["market"] != market:
                continue
            merged.setdefault((r["market"], r["ticker"]), r)

    return list(merged.values())[:limit]
