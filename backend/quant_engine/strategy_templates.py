"""策略模板 — 预配置的可复用策略组合（回测一键套用）

每个模板 = 策略 + 参数 + 建议标的 + 再平衡频率。前端「回测」页提供模板选择，
点击即填入表单，也可再手动调整。
"""
from typing import Any, Dict, List

# 建议标的（高流动性，可手动改）
_BLUECHIP = [
    "600519", "000001", "601318", "600036", "000858",
    "600887", "601012", "002594", "300750", "600900",
]

TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "value_dividend",
        "name": "低估值红利",
        "description": "按 PE 低估排名选 Top 10 等权持有，月度再平衡（价值风格）",
        "strategy": "factor_rank",
        "params": {"factor": "pe_ttm", "top_n": 10},
        "tickers": list(_BLUECHIP),
        "rebalance_freq": "monthly",
    },
    {
        "id": "trend_follow",
        "name": "双均线趋势",
        "description": "MA5/MA20 金叉买入、死叉空仓，适合单标的趋势跟踪",
        "strategy": "ma_cross",
        "params": {"fast": 5, "slow": 20},
        "tickers": ["600519"],
        "rebalance_freq": "daily",
    },
    {
        "id": "momentum_top",
        "name": "动量优选",
        "description": "按 20 日动量排名选 Top 10 等权持有，月度再平衡（动量风格）",
        "strategy": "factor_rank",
        "params": {"factor": "momentum_20d", "top_n": 10},
        "tickers": list(_BLUECHIP),
        "rebalance_freq": "monthly",
    },
    {
        "id": "equal_weight",
        "name": "等权一篮子",
        "description": "等权持有全部输入标的，不择时不调仓（基准对照用）",
        "strategy": "equal_weight",
        "params": {},
        "tickers": list(_BLUECHIP),
        "rebalance_freq": "monthly",
    },
]


def get_templates() -> List[Dict[str, Any]]:
    """返回模板列表（副本，避免外部修改）"""
    return [dict(t) for t in TEMPLATES]


def validate_template(template_id: str) -> bool:
    return any(t["id"] == template_id for t in TEMPLATES)
