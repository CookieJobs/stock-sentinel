"""同花顺增强 API — 财务指标 enrichment / 异动归因"""
from fastapi import APIRouter, HTTPException

from .. import ths_service

router = APIRouter(prefix="/ths", tags=["ths"])


@router.post("/indicators/refresh")
def refresh_indicators(tickers: str = ""):
    """拉取财务指标并缓存：POST /api/quant/ths/indicators/refresh?tickers=600519,000001
    不传 tickers 时刷新监控列表"""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        ticker_list = ths_service.get_monitored_tickers()
    if not ticker_list:
        raise HTTPException(status_code=400, detail="监控列表为空且未指定 tickers")
    n = ths_service.refresh_indicators(ticker_list)
    return {"refreshed": n, "total": len(ticker_list)}


@router.get("/indicators")
def get_indicators(tickers: str):
    """查询缓存指标：GET /api/quant/ths/indicators?tickers=600519,000001"""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="请指定 tickers")
    return {"indicators": ths_service.get_cached_indicators(ticker_list)}
