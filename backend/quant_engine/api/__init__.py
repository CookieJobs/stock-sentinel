"""量化引擎 API 路由聚合"""
from fastapi import APIRouter

# 5 个子路由（M0 阶段只有占位接口，M1+ 逐步充实）
from . import kline, factors, backtest, portfolio, risk, indicators, metrics, events, paper, ths, datasource

api_router = APIRouter(prefix="/api/quant", tags=["quant"])
api_router.include_router(kline.router)
api_router.include_router(factors.router)
api_router.include_router(backtest.router)
api_router.include_router(portfolio.router)
api_router.include_router(risk.router)
api_router.include_router(indicators.router)
api_router.include_router(metrics.router)
api_router.include_router(events.router)
api_router.include_router(paper.router)
api_router.include_router(ths.router)
api_router.include_router(datasource.router)
