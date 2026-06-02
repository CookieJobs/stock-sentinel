"""多因子 API（M0 占位，M3 充实）"""
from fastapi import APIRouter

from ..factors import list_factors

router = APIRouter(prefix="/factors", tags=["factors"])


@router.get("/list")
def list_all():
    """列出所有因子"""
    return {"factors": list_factors()}


@router.post("/screen")
def screen(payload: dict):
    """选股：按因子筛选 + 排名（M0 占位，M3 充实）"""
    return {
        "filters": payload.get("filters", []),
        "rank_by": payload.get("rank_by"),
        "top_n": payload.get("top_n", 20),
        "results": [],
        "message": "M3 实现：基于 daily_metrics + factor_values 跑多因子选股",
    }
