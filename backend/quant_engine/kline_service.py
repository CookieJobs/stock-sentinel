"""K 线服务层 — 封装"获取 → 入库 → 缓存"逻辑

- get_or_fetch(): 优先查本地 SQLite（kline 表），无最新数据再调用 data_source
- 简单 LRU 内存缓存（按 ticker+period+adj 缓存 5 分钟）
- 入库：UNIQUE (ticker, market, period, adj, trade_date)，重复自动 UPSERT
- compute_indicators_inline(): K 线 + 指标 一次性返回（前端无需自己算）
"""
from __future__ import annotations
import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from .db import get_quant_db
from .data_source import get_kline as _get_kline_remote
from .indicators import compute as compute_indicator, INDICATORS

logger = logging.getLogger(__name__)


# ── 简单 LRU 缓存（避免高并发重复拉取） ─────────────────────────

class _LruCache:
    def __init__(self, max_size: int = 128, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self._data: OrderedDict[str, tuple[float, pd.DataFrame]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[pd.DataFrame]:
        with self._lock:
            if key not in self._data:
                return None
            ts, df = self._data[key]
            if time.time() - ts > self.ttl:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return df

    def set(self, key: str, df: pd.DataFrame):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (time.time(), df)
            if len(self._data) > self.max_size:
                self._data.popitem(last=False)

    def clear(self):
        with self._lock:
            self._data.clear()


_kline_cache = _LruCache(max_size=128, ttl=300)


# ── 入库 ──────────────────────────────────────────────────────

def _upsert_kline(df: pd.DataFrame) -> int:
    """把 K 线 DataFrame 写入 SQLite（UPSERT 语义）。返回入库行数。"""
    if df is None or df.empty:
        return 0
    db = get_quant_db()
    try:
        cur = db.cursor()
        rows = []
        for _, r in df.iterrows():
            rows.append((
                r["ticker"], r["market"], r["period"], r["adj"],
                r["trade_date"],
                r.get("open"), r.get("high"), r.get("low"),
                r.get("close"), r.get("volume"), r.get("amount"),
            ))
        cur.executemany(
            """INSERT OR REPLACE INTO kline
               (ticker, market, period, adj, trade_date,
                open, high, low, close, volume, amount)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        db.commit()
        return cur.rowcount
    finally:
        db.close()


def _query_local_kline(ticker: str, market: str, period: str, adj: str,
                       start: Optional[str], end: Optional[str]) -> pd.DataFrame:
    """从本地 SQLite 查 K 线"""
    db = get_quant_db()
    try:
        sql = "SELECT * FROM kline WHERE ticker=? AND market=? AND period=? AND adj=?"
        params = [ticker.upper(), market, period, adj]
        if start:
            sql += " AND trade_date >= ?"
            params.append(start)
        if end:
            sql += " AND trade_date <= ?"
            params.append(end)
        sql += " ORDER BY trade_date"
        rows = db.execute(sql, params).fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])
    finally:
        db.close()


# ── 入口：智能获取 ───────────────────────────────────────────

def get_or_fetch(ticker: str, market: str, period: str = "1d",
                 start: Optional[str] = None, end: Optional[str] = None,
                 adj: str = "qfq", *, force_remote: bool = False) -> pd.DataFrame:
    """获取 K 线：先查本地 DB，再补远程缺失部分，最后入库

    Args:
        ticker: 股票代码
        market: US / CN / HK
        period: 1d / 1w / 1mo / 1m / 5m / 15m / 30m / 60m
        start, end: YYYY-MM-DD
        adj: qfq / hfq / none
        force_remote: 跳过本地查询，直接拉远程
    """
    ticker = ticker.upper().replace(".HK", "")
    cache_key = f"{ticker}:{market}:{period}:{adj}:{start or ''}:{end or ''}"

    # 1. 内存缓存
    cached = _kline_cache.get(cache_key)
    if cached is not None and not force_remote:
        return cached

    # 2. 本地 DB
    local_df = pd.DataFrame() if force_remote else _query_local_kline(ticker, market, period, adj, start, end)

    # 3. 判断是否需要拉远程
    need_remote = force_remote or local_df.empty or _is_stale(local_df, period)
    if not need_remote:
        _kline_cache.set(cache_key, local_df)
        return local_df

    # 4. 远程拉取
    try:
        remote_df = _get_kline_remote(ticker, market, period, start, end, adj)
    except Exception as e:
        logger.warning("Remote kline fetch failed for %s/%s: %s", ticker, market, e)
        if not local_df.empty:
            _kline_cache.set(cache_key, local_df)
            return local_df
        return pd.DataFrame()

    if remote_df is None or remote_df.empty:
        if not local_df.empty:
            _kline_cache.set(cache_key, local_df)
            return local_df
        return pd.DataFrame()

    # 5. 补齐 meta 列（入库需要）
    remote_df = remote_df.copy()
    remote_df["ticker"] = ticker
    remote_df["market"] = market
    remote_df["period"] = period
    remote_df["adj"] = adj

    # 6. 入库
    try:
        inserted = _upsert_kline(remote_df)
        logger.info("Upserted %d kline rows for %s/%s/%s/%s", inserted, ticker, market, period, adj)
    except Exception as e:
        logger.warning("Failed to upsert kline: %s", e)

    # 7. 合并本地 + 远程（去重按 trade_date）
    if not local_df.empty:
        merged = pd.concat([local_df, remote_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=["trade_date"], keep="last")
        merged = merged.sort_values("trade_date").reset_index(drop=True)
    else:
        merged = remote_df.sort_values("trade_date").reset_index(drop=True)

    # 8. 应用 start/end 过滤
    if start:
        merged = merged[merged["trade_date"] >= start]
    if end:
        merged = merged[merged["trade_date"] <= end]

    _kline_cache.set(cache_key, merged)
    return merged


def _is_stale(df: pd.DataFrame, period: str) -> bool:
    """判断本地数据是否过期（最新一根 K 线是否太旧）"""
    if df.empty:
        return True
    last_date_str = df["trade_date"].iloc[-1]
    try:
        last_date = datetime.strptime(last_date_str.split(" ")[0], "%Y-%m-%d")
    except (ValueError, AttributeError):
        return True
    # 不同周期的"新鲜"阈值
    threshold_days = {
        "1d": 1, "1w": 7, "1mo": 31,
        "60m": 1, "30m": 1, "15m": 1, "5m": 1, "1m": 1,
    }.get(period, 1)
    age = (datetime.now() - last_date).days
    return age > threshold_days


# ── K 线元信息 ──────────────────────────────────────────────

def get_kline_meta(ticker: str, market: str, period: str, adj: str = "qfq") -> dict:
    """K 线元信息：覆盖范围、记录数、最新日期、过期？"""
    df = _query_local_kline(ticker, market, period, adj, None, None)
    if df.empty:
        return {
            "ticker": ticker.upper(),
            "market": market,
            "period": period,
            "adj": adj,
            "row_count": 0,
            "first_date": None,
            "last_date": None,
            "is_stale": True,
        }
    return {
        "ticker": ticker.upper(),
        "market": market,
        "period": period,
        "adj": adj,
        "row_count": len(df),
        "first_date": str(df["trade_date"].iloc[0]),
        "last_date": str(df["trade_date"].iloc[-1]),
        "is_stale": _is_stale(df, period),
    }


# ── K 线 + 指标 联合 ───────────────────────────────────────

def get_kline_with_indicators(
    ticker: str, market: str, period: str = "1d",
    start: Optional[str] = None, end: Optional[str] = None,
    adj: str = "qfq",
    indicator_specs: Optional[list[dict]] = None,
) -> dict:
    """一次性返回 K 线 + 多个技术指标

    indicator_specs: [{"name": "MA", "params": {"period": 5}}, ...]
    """
    df = get_or_fetch(ticker, market, period, start, end, adj)
    if df.empty:
        return {"kline": [], "indicators": {}, "meta": get_kline_meta(ticker, market, period, adj)}

    # 基础 K 线（按 trade_date 升序）
    kline = []
    for _, r in df.iterrows():
        kline.append({
            "time": r["trade_date"],
            "open": _to_float(r.get("open")),
            "high": _to_float(r.get("high")),
            "low":  _to_float(r.get("low")),
            "close": _to_float(r.get("close")),
            "volume": _to_float(r.get("volume")),
        })

    # 指标
    indicator_data = {}
    if indicator_specs:
        for spec in indicator_specs:
            name = spec.get("name")
            params = spec.get("params", {})
            if name not in INDICATORS:
                continue
            try:
                meta = INDICATORS[name]
                inputs = {col: df[col] for col in meta["inputs"] if col in df.columns}
                if len(inputs) != len(meta["inputs"]):
                    continue
                result = meta["fn"](**inputs, **params)
                # 单 Series / dict（multi）
                if isinstance(result, dict):
                    for k, v in result.items():
                        indicator_data[f"{name}.{k}"] = {
                            "name": f"{name}.{k}",
                            "params": params,
                            "values": [
                                {"time": t, "value": _to_float(val)}
                                for t, val in zip(df["trade_date"], v)
                                if pd.notna(val)
                            ],
                        }
                else:
                    indicator_data[name] = {
                        "name": name,
                        "params": params,
                        "values": [
                            {"time": t, "value": _to_float(val)}
                            for t, val in zip(df["trade_date"], result)
                            if pd.notna(val)
                        ],
                    }
            except Exception as e:
                logger.warning("Indicator %s compute failed: %s", name, e)

    return {
        "kline": kline,
        "indicators": indicator_data,
        "meta": get_kline_meta(ticker, market, period, adj),
    }


def _to_float(v):
    try:
        if v is None or (isinstance(v, float) and (v != v)):  # NaN
            return None
        return round(float(v), 4)
    except (ValueError, TypeError):
        return None
