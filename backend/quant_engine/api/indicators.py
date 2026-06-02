"""技术指标 API（M0 占位，M2 充实）"""
from fastapi import APIRouter

from ..indicators import list_indicators, compute
import pandas as pd

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("/list")
def list_all():
    """列出所有可用指标"""
    return {"indicators": list_indicators()}


@router.post("/compute")
def compute_indicator(payload: dict):
    """计算指定指标（M0 占位，M2 充实）"""
    return {
        "name": payload.get("name"),
        "params": payload.get("params", {}),
        "result": {},
        "message": "M2 实现：完整指标计算 + 返回 Series",
    }
