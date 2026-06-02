"""风险指标 API（M0 占位，M5 充实）"""
from fastapi import APIRouter

from ..risk import compute_all, compute_trade_stats, list_benchmarks

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/benchmarks")
def benchmarks():
    """列出所有支持的基准"""
    return {"benchmarks": list_benchmarks()}


@router.post("/compute")
def compute(payload: dict):
    """计算风险指标"""
    equity_curve = payload.get("equity_curve", [])
    initial_capital = payload.get("initial_capital", 1_000_000)
    metrics = compute_all(equity_curve, initial_capital)
    if "trades" in payload:
        trade_stats = compute_trade_stats(payload["trades"])
        metrics.update(trade_stats)
    return metrics
