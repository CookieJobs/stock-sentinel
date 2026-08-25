"""AI 策略选股 API（v1.1）

GET  /api/quant/screener/strategies            - 内置策略列表 + LLM 是否可用
POST /api/quant/screener/strategies/generate   - 自然语言 → AI 生成策略
POST /api/quant/screener/screen                - 按策略一键选股（strategy_id 或完整策略对象）
"""
from fastapi import APIRouter, HTTPException

from ..screener_strategies import (
    StrategyError,
    apply_strategy,
    generate_strategy,
    get_strategies,
    get_strategy,
    llm_configured,
    validate_strategy,
)

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("/strategies")
def list_strategies():
    """内置策略列表（新手一键选股用）"""
    return {"strategies": get_strategies(), "llm_configured": llm_configured()}


@router.post("/strategies/generate")
def generate(payload: dict):
    """自然语言描述 → AI 生成选股策略

    payload: {"prompt": "我想找低估值的高分红股"}
    """
    try:
        strategy = generate_strategy(payload.get("prompt", ""))
    except StrategyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"strategy": strategy}


@router.post("/screen")
def screen_with_strategy(payload: dict):
    """按策略一键选股

    payload: {"strategy_id": "value_quality"} 或 {"strategy": {...完整策略对象}}
    """
    try:
        if payload.get("strategy_id"):
            strategy = get_strategy(payload["strategy_id"])
        elif payload.get("strategy"):
            strategy = payload["strategy"]
            validate_strategy(strategy)
        else:
            raise StrategyError("请提供 strategy_id 或 strategy")
    except StrategyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return apply_strategy(strategy)
