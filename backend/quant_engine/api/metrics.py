"""统一指标查询 API（M0 占位）"""
from fastapi import APIRouter

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/health")
def health():
    return {"module": "metrics", "status": "ok"}


@router.get("/dashboard")
def dashboard():
    """Dashboard 综合指标（M0 占位，M5 充实）"""
    return {
        "total_strategies": 0,
        "total_portfolios": 0,
        "total_backtests": 0,
        "active_alerts": 0,
        "message": "M5 实现：综合 Dashboard",
    }
