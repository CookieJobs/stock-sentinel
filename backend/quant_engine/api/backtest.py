"""回测 API（M0 占位，M4 充实）"""
from fastapi import APIRouter

from ..backtest import SIGNAL_REGISTRY

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/strategies")
def list_strategies():
    """列出所有可用策略"""
    return {
        "strategies": [
            {"name": k, "default_params": v["default_params"], "description": v["description"]}
            for k, v in SIGNAL_REGISTRY.items()
        ]
    }


@router.post("/run")
def run(payload: dict):
    """运行回测（M0 占位，M4 充实）"""
    return {
        "backtest_id": None,
        "status": "pending",
        "message": "M4 实现：调用 quant_engine.backtest.run_backtest",
    }


@router.get("/{backtest_id}")
def get_result(backtest_id: int):
    """获取回测结果"""
    return {
        "backtest_id": backtest_id,
        "status": "pending",
        "message": "M4 实现",
    }
