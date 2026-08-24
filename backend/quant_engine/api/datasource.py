"""数据源配置 API — 用户主动选择各数据域的数据源"""
from fastapi import APIRouter, HTTPException

from datasource_config import get_config, set_override

router = APIRouter(prefix="/datasource", tags=["datasource"])


@router.get("/config")
def config():
    """查询配置：{domains: {realtime: {mode, source, options}, ...}}"""
    return {"domains": get_config()}


@router.put("/config")
def update_config(payload: dict):
    """设置：PUT /api/quant/datasource/config {realtime: "tencent", factor: "auto", ...}"""
    errors = []
    for domain, source in payload.items():
        try:
            set_override(domain, source)
        except ValueError as e:
            errors.append(str(e))
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return {"domains": get_config()}
