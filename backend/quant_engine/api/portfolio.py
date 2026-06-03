"""组合 API（M5 完整版）

GET  /api/quant/portfolios/{id}/valuation    - 组合估值
GET  /api/quant/portfolios/{id}/rebalance    - 再平衡操作建议
POST /api/quant/portfolios/{id}/run-backtest - 用组合跑回测
（其余 CRUD 沿用 M0 的实现）
"""
from fastapi import APIRouter, HTTPException
from typing import Optional

from ..portfolio import (
    list_portfolios, create_portfolio, get_portfolio, delete_portfolio,
    add_holding, update_holding_weight, remove_holding,
)
from ..portfolio_service import valuation, rebalance_actions, to_backtest_payload
from ..backtest_service import submit as submit_backtest

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.get("/health")
def health():
    return {"module": "portfolios", "status": "ok", "version": "M5"}


@router.get("/")
def list_all():
    return {"portfolios": list_portfolios()}


@router.post("/")
def create(payload: dict):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name 不能为空")
    pid = create_portfolio(
        name=name,
        description=payload.get("description", ""),
        benchmark=payload.get("benchmark", "000300.SH"),
        rebalance_freq=payload.get("rebalance_freq", "monthly"),
    )
    return {"id": pid}


@router.get("/{portfolio_id}")
def get(portfolio_id: int):
    p = get_portfolio(portfolio_id)
    if not p:
        raise HTTPException(status_code=404, detail="组合不存在")
    return p


@router.delete("/{portfolio_id}")
def delete(portfolio_id: int):
    ok = delete_portfolio(portfolio_id)
    if not ok:
        raise HTTPException(status_code=404, detail="组合不存在")
    return {"deleted": True}


@router.post("/{portfolio_id}/holdings")
def add_h(portfolio_id: int, payload: dict):
    ticker = (payload.get("ticker") or "").strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker 不能为空")
    add_holding(portfolio_id, ticker, market=payload.get("market", "CN"),
                weight=payload.get("weight", 0))
    return {"added": True}


@router.put("/{portfolio_id}/holdings/{ticker}")
def update_h(portfolio_id: int, ticker: str, payload: dict):
    ok = update_holding_weight(portfolio_id, ticker, payload.get("weight", 0))
    if not ok:
        raise HTTPException(status_code=404, detail="持仓不存在")
    return {"updated": True}


@router.delete("/{portfolio_id}/holdings/{ticker}")
def remove_h(portfolio_id: int, ticker: str):
    ok = remove_holding(portfolio_id, ticker)
    if not ok:
        raise HTTPException(status_code=404, detail="持仓不存在")
    return {"removed": True}


@router.get("/{portfolio_id}/valuation")
def get_valuation(portfolio_id: int):
    """组合估值（实时价 + 持仓权重）"""
    return valuation(portfolio_id)


@router.get("/{portfolio_id}/rebalance")
def get_rebalance(portfolio_id: int, threshold: float = 0.05,
                  total_capital: float = 1_000_000):
    """再平衡操作建议（基于当前价 vs 目标权重）"""
    return {
        "portfolio_id": portfolio_id,
        "actions": rebalance_actions(portfolio_id, total_capital, threshold),
        "threshold": threshold,
    }


@router.post("/{portfolio_id}/run-backtest")
def run_portfolio_backtest(portfolio_id: int, payload: dict = None):
    """用组合跑回测（按持仓权重，fixed_weights 策略）"""
    payload = payload or {}
    try:
        bt_payload = to_backtest_payload(
            portfolio_id,
            start_date=payload.get("start_date", "2024-01-01"),
            end_date=payload.get("end_date", "2024-12-31"),
            initial_capital=payload.get("initial_capital", 1_000_000),
            benchmark=payload.get("benchmark"),
            rebalance_freq=payload.get("rebalance_freq", "monthly"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    backtest_id = submit_backtest(**bt_payload)
    return {
        "backtest_id": backtest_id,
        "portfolio_id": portfolio_id,
        "status": "pending",
        "message": "组合回测已提交；前往'回测'页面查看结果",
    }
