"""组合 API（M0 占位，M5 充实）"""
from fastapi import APIRouter

from ..portfolio import list_portfolios, create_portfolio, get_portfolio, delete_portfolio

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.get("/")
def list_all():
    return {"portfolios": list_portfolios()}


@router.post("/")
def create(payload: dict):
    pid = create_portfolio(
        name=payload.get("name", "未命名组合"),
        description=payload.get("description", ""),
        benchmark=payload.get("benchmark", "000300.SH"),
        rebalance_freq=payload.get("rebalance_freq", "monthly"),
    )
    return {"id": pid}


@router.get("/{portfolio_id}")
def get(portfolio_id: int):
    p = get_portfolio(portfolio_id)
    if not p:
        return {"error": "not found"}
    return p


@router.delete("/{portfolio_id}")
def delete(portfolio_id: int):
    ok = delete_portfolio(portfolio_id)
    return {"deleted": ok}


@router.post("/{portfolio_id}/holdings")
def add_holding(portfolio_id: int, payload: dict):
    ok = add_holding(portfolio_id, payload.get("ticker", ""),
                    market=payload.get("market", "CN"),
                    weight=payload.get("weight", 0.0))
    return {"added": ok}


@router.post("/{portfolio_id}/rebalance-check")
def rebalance_check(portfolio_id: int, payload: dict):
    """检查再平衡需求"""
    prices = payload.get("current_prices", {})
    threshold = payload.get("threshold", 0.05)
    return check_rebalance(portfolio_id, prices, threshold)
