"""回测 API（M4 充实版）

POST /api/quant/backtest/run         - 提交回测任务
GET  /api/quant/backtest/{id}        - 获取回测结果
GET  /api/quant/backtest/list/recent - 列出最近回测
GET  /api/quant/backtest/strategies  - 列出可用策略（已有）
"""
from fastapi import APIRouter, HTTPException
from typing import Optional

from ..backtest import SIGNAL_REGISTRY
from ..backtest_service import submit, fetch, list_recent

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/health")
def health():
    return {"module": "backtest", "status": "ok", "version": "M4"}


@router.get("/strategies")
def list_strategies():
    return {
        "strategies": [
            {"name": k, "default_params": v["default_params"], "description": v["description"]}
            for k, v in SIGNAL_REGISTRY.items()
        ]
    }


@router.post("/run")
def run_backtest(payload: dict):
    """提交回测任务（异步执行）"""
    required = ["name", "strategy", "tickers", "start_date", "end_date"]
    for k in required:
        if k not in payload:
            raise HTTPException(status_code=400, detail=f"Missing field: {k}")

    try:
        backtest_id = submit(
            name=payload["name"],
            strategy=payload["strategy"],
            params=payload.get("params", {}),
            tickers=payload["tickers"],
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            initial_capital=payload.get("initial_capital", 1_000_000),
            commission=payload.get("commission", 0.0003),
            slippage=payload.get("slippage", 0.001),
            benchmark=payload.get("benchmark", "000300.SH"),
            market=payload.get("market", "CN"),
            rebalance_freq=payload.get("rebalance_freq", "monthly"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "backtest_id": backtest_id,
        "status": "pending",
        "message": "回测任务已提交，后台异步执行；通过 GET /backtest/{id} 轮询结果",
    }


@router.get("/list/recent")
def recent(limit: int = 20):
    """列出最近 N 个回测"""
    return {"backtests": list_recent(limit)}


@router.get("/{backtest_id}")
def get_backtest(backtest_id: int):
    """获取回测任务状态 + 结果"""
    result = fetch(backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail="回测任务不存在")
    return result
