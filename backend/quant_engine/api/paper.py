"""模拟交易（Paper Trading）API"""
from fastapi import APIRouter, HTTPException

from .. import paper_service

router = APIRouter(prefix="/paper", tags=["paper"])


@router.get("")
def list_paper():
    """组合列表"""
    return {"portfolios": paper_service.list_portfolios()}


@router.post("", status_code=201)
def create_paper(payload: dict):
    """创建模拟组合 {name, initial_capital}"""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="组合名称不能为空")
    try:
        capital = float(payload.get("initial_capital", 100000))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="初始资金格式错误")
    if capital <= 0:
        raise HTTPException(status_code=400, detail="初始资金必须大于 0")
    return paper_service.create_portfolio(name, capital)


@router.get("/{portfolio_id}")
def get_paper(portfolio_id: int):
    """组合详情（持仓实时价 + 成交 + 净值曲线）"""
    detail = paper_service.get_detail(portfolio_id)
    if not detail:
        raise HTTPException(status_code=404, detail="组合不存在")
    return detail


@router.post("/{portfolio_id}/trade")
def paper_trade(portfolio_id: int, payload: dict):
    """模拟下单 {ticker, side, qty}（真实行情成交，demo 拒绝）"""
    try:
        return paper_service.trade(
            portfolio_id,
            payload.get("ticker", ""),
            payload.get("side", ""),
            float(payload.get("qty", 0)),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{portfolio_id}/mark")
def paper_mark(portfolio_id: int):
    """按最新行情重估净值"""
    try:
        return paper_service.mark_to_market(portfolio_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{portfolio_id}/close")
def paper_close(portfolio_id: int):
    """关闭组合（不再交易）"""
    if not paper_service.close_portfolio(portfolio_id):
        raise HTTPException(status_code=404, detail="组合不存在或已关闭")
    return {"detail": "已关闭"}


@router.delete("/{portfolio_id}")
def paper_delete(portfolio_id: int):
    """删除组合（连带持仓/成交/净值）"""
    if not paper_service.delete_portfolio(portfolio_id):
        raise HTTPException(status_code=404, detail="组合不存在")
    return {"detail": "已删除"}
