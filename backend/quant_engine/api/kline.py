"""K 线 API（M1 充实版）

GET  /api/quant/kline/{ticker}              - 获取 K 线（自动远程拉取 + 入库）
GET  /api/quant/kline/{ticker}/meta         - K 线元信息
POST /api/quant/kline/{ticker}/with-indicators - K 线 + 指标 联合
POST /api/quant/kline/cache/clear           - 清内存缓存
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ..kline_service import (
    get_or_fetch, get_kline_meta, get_kline_with_indicators, _kline_cache,
)

router = APIRouter(prefix="/kline", tags=["kline"])


@router.get("/health")
def health():
    return {"module": "kline", "status": "ok", "version": "M1"}


@router.get("/{ticker}")
def get_kline(
    ticker: str,
    market: str = Query("CN", pattern="^(US|CN|HK)$"),
    period: str = Query("1d", pattern="^(1d|1w|1mo|1m|5m|15m|30m|60m)$"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    adj: str = Query("qfq", pattern="^(qfq|hfq|none)$"),
    force: bool = False,
):
    """获取 K 线（自动远程拉取 + 入库 + 内存缓存）"""
    try:
        df = get_or_fetch(ticker, market, period, start, end, adj, force_remote=force)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"K 线获取失败: {e}")
    if df.empty:
        return {
            "ticker": ticker.upper(),
            "market": market,
            "period": period,
            "adj": adj,
            "row_count": 0,
            "first_date": None,
            "last_date": None,
            "rows": [],
            "message": "暂无数据（可能未配置 API key 或网络不可达）",
        }
    rows = df[["trade_date", "open", "high", "low", "close", "volume", "amount"]].to_dict("records")
    return {
        "ticker": ticker.upper(),
        "market": market,
        "period": period,
        "adj": adj,
        "row_count": len(rows),
        "first_date": str(df["trade_date"].iloc[0]),
        "last_date": str(df["trade_date"].iloc[-1]),
        "rows": rows,
    }


@router.get("/{ticker}/meta")
def kline_meta(
    ticker: str,
    market: str = Query("CN", pattern="^(US|CN|HK)$"),
    period: str = Query("1d", pattern="^(1d|1w|1mo|1m|5m|15m|30m|60m)$"),
    adj: str = Query("qfq", pattern="^(qfq|hfq|none)$"),
):
    """K 线元信息（覆盖范围、是否过期）"""
    return get_kline_meta(ticker, market, period, adj)


@router.post("/{ticker}/with-indicators")
def kline_with_indicators(
    ticker: str,
    payload: dict = None,
    market: str = Query("CN", pattern="^(US|CN|HK)$"),
    period: str = Query("1d", pattern="^(1d|1w|1mo|1m|5m|15m|30m|60m)$"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    adj: str = Query("qfq", pattern="^(qfq|hfq|none)$"),
):
    """K 线 + 多个指标 一次性返回

    payload: {"indicators": [{"name": "MA", "params": {"period": 5}}, ...]}
    """
    payload = payload or {}
    indicator_specs = payload.get("indicators", [])
    try:
        result = get_kline_with_indicators(ticker, market, period, start, end, adj, indicator_specs)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"K 线+指标获取失败: {e}")
    return {
        "ticker": ticker.upper(),
        "market": market,
        "period": period,
        "adj": adj,
        **result,
    }


@router.post("/cache/clear")
def clear_cache():
    """清内存缓存（开发调试用）"""
    _kline_cache.clear()
    return {"cleared": True}
