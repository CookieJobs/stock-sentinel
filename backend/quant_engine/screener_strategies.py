"""AI 策略选股 — 新手友好的选股策略库（v1.1）

三件事：
1. 内置策略（专家预写，确定性、无 LLM Key 也可用）：每个策略 = 人话名字 + tagline +
   适用人群 + 过滤条件组（filters + rank_by + top_n）+ 每个条件的白话解释。
2. 自然语言生成策略：用户一句话描述想要的股票 → LLM 转结构化策略 JSON → 严格校验
   （因子必须存在于 FACTOR_REGISTRY、数值范围合法）→ 返回可执行的策略卡。
3. 策略执行：整列为空的筛选因子自动跳过（数据源没给这个字段时，不因缺数据静默
   返回 0 只），并如实返回 skipped_factors。

LLM 配置复用 briefing 的 OpenAI 兼容接口（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL），
不引入新的外部服务；无 Key 或失败时抛 StrategyError，由 API 层转成友好 400。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests

from .factors import FACTOR_EXPLAINERS, FACTOR_REGISTRY

logger = logging.getLogger(__name__)

# LLM 配置复用 briefing（单一事实源）
from briefing import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


class StrategyError(Exception):
    """策略校验 / 生成失败（业务错误，转 HTTP 400）"""


# daily_metrics 表里有、但不在 FACTOR_REGISTRY 的附加筛选/排名字段
# （注册因子用于因子计算与截面排名；这些字段只能直接筛/排，不参与因子计算）
EXTRA_SCREEN_FIELDS = {"market_cap", "peg", "free_cash_flow"}
SCREENABLE_FIELDS = set(FACTOR_REGISTRY) | EXTRA_SCREEN_FIELDS


# ── 内置策略 ──────────────────────────────────────────────────
# 单位约定（与当前库实测一致）：PE/PB/PS 为倍；ROE/毛利率/负债率/换手率为百分比原值。
# 条件为"或松"设计：某个因子整列为空时自动跳过（见 apply_strategy），保证结果不塌方。

SCREENER_STRATEGIES: List[Dict[str, Any]] = [
    {
        "id": "value_quality",
        "name": "便宜又赚钱的好公司",
        "emoji": "🛒",
        "tagline": "估值不贵 + 赚钱能力强，适合想长期持有的稳健投资者",
        "audience": "稳健型 · 想拿住 1 年以上",
        "risk_level": "中低",
        "filters": [
            {"factor": "pe_ttm", "max": 25},
            {"factor": "pb", "max": 4},
            {"factor": "roe", "min": 12},
        ],
        "rank_by": "roe",
        "top_n": 20,
        "why": "好公司 = 会赚钱（ROE 高）且不贵（PE/PB 低）。在便宜的价格买入好公司，长期持有更安心，这也是价值投资的经典思路。",
        "explains": {
            "pe_ttm": "PE ≤ 25：市盈率 25 倍以内，相当于按当前赚钱速度 25 年回本，属于「不算贵」",
            "pb": "PB ≤ 4：市净率 4 倍以内，为公司的家底付的价格不离谱",
            "roe": "ROE ≥ 12：公司用股东的钱一年至少赚 12%，赚钱能力优于多数公司",
        },
    },
    {
        "id": "steady_growth",
        "name": "稳健成长股",
        "emoji": "🌱",
        "tagline": "赚钱效率高 + 产品能卖上价，适合追求成长的投资者",
        "audience": "成长型 · 能承受一定波动",
        "risk_level": "中",
        "filters": [
            {"factor": "pe_ttm", "max": 40},
            {"factor": "roe", "min": 15},
            {"factor": "gross_margin", "min": 30},
        ],
        "rank_by": "roe",
        "top_n": 20,
        "why": "好成长股要「又强又贵得有理」：ROE 15% 以上证明赚钱效率高，毛利率 30% 以上说明产品有定价权，估值给到 40 倍以内不算离谱。",
        "explains": {
            "pe_ttm": "PE ≤ 40：成长股估值可以贵一些，但 40 倍是「合理偏贵」的界限",
            "roe": "ROE ≥ 15：赚钱效率一流，超过大多数上市公司",
            "gross_margin": "毛利率 ≥ 30%：卖 100 元货至少毛赚 30 元，产品有定价权、不容易打价格战",
        },
    },
    {
        "id": "deep_value",
        "name": "深度低估股",
        "emoji": "🏦",
        "tagline": "捡便宜货：估值极低，适合喜欢逆向布局的投资者",
        "audience": "逆向型 · 能接受短期不涨",
        "risk_level": "中高",
        "filters": [
            {"factor": "pe_ttm", "max": 15},
            {"factor": "pb", "max": 2},
        ],
        "rank_by": "pe_ttm",
        "top_n": 20,
        "why": "市场情绪低迷时好公司也会被错杀。PE 15 倍、PB 2 倍以内属于深度低估区间，按「最便宜的」排序，适合逆向布局。注意：便宜可能继续便宜，要有耐心。",
        "explains": {
            "pe_ttm": "PE ≤ 15：15 年以内回本，属于市场公认的低估区间",
            "pb": "PB ≤ 2：价格不到净资产的 2 倍，接近「按家底打折买」",
        },
    },
    {
        "id": "big_stable",
        "name": "大盘稳健蓝筹",
        "emoji": "🏔",
        "tagline": "大公司 + 赚钱稳定，适合刚入门的新手",
        "audience": "新手 · 求稳",
        "risk_level": "低",
        "filters": [
            {"factor": "market_cap", "min": 300},
            {"factor": "roe", "min": 10},
            {"factor": "pe_ttm", "max": 30},
        ],
        "rank_by": "market_cap",
        "top_n": 20,
        "why": "大公司抗风险能力强、经营更稳定，是新手熟悉市场的好起点。按市值排序，先看最大最稳的一批。",
        "explains": {
            "market_cap": "市值 ≥ 300 亿：大公司，机构关注多、流动性好、倒闭风险低",
            "roe": "ROE ≥ 10：赚钱能力跑赢通胀和多数公司",
            "pe_ttm": "PE ≤ 30：估值不离谱，不追高",
        },
    },
    {
        "id": "quality_moat",
        "name": "高毛利护城河",
        "emoji": "🏰",
        "tagline": "产品有定价权、别人抢不走生意，适合看重竞争壁垒的投资者",
        "audience": "价值质量型",
        "risk_level": "中",
        "filters": [
            {"factor": "gross_margin", "min": 40},
            {"factor": "roe", "min": 12},
            {"factor": "pe_ttm", "max": 50},
        ],
        "rank_by": "gross_margin",
        "top_n": 20,
        "why": "毛利率 40% 以上意味着产品有护城河（品牌/技术/牌照），对手难以抢生意。这类公司往往能长期稳定赚钱。",
        "explains": {
            "gross_margin": "毛利率 ≥ 40%：卖 100 元货毛赚 40 元以上，定价权强、护城河深",
            "roe": "ROE ≥ 12：护城河要能转化成真金白银的赚钱能力",
            "pe_ttm": "PE ≤ 50：好公司也怕买贵，50 倍封顶",
        },
    },
    {
        "id": "low_debt_safe",
        "name": "低负债稳如泰山",
        "emoji": "🛡",
        "tagline": "几乎不借钱经营，财务最稳健，适合极度保守的投资者",
        "audience": "保守型 · 极度求稳",
        "risk_level": "低",
        "filters": [
            {"factor": "debt_ratio", "max": 40},
            {"factor": "pe_ttm", "max": 30},
            {"factor": "roe", "min": 8},
        ],
        "rank_by": "debt_ratio",
        "top_n": 20,
        "why": "资产负债率 40% 以内意味着公司主要靠自己的钱经营，不怕加息、不怕行业寒冬。按负债率从低到高排序，挑最「干净」的公司。",
        "explains": {
            "debt_ratio": "负债率 ≤ 40%：资产里借来的钱不到四成，财务结构稳健",
            "pe_ttm": "PE ≤ 30：估值合理，不为稳健付太高的溢价",
            "roe": "ROE ≥ 8：不借钱也能赚到 8% 以上，经营是真本事",
        },
    },
]


def get_strategies() -> List[Dict[str, Any]]:
    """返回内置策略列表（深拷贝副本，避免外部修改）"""
    return [json.loads(json.dumps(s)) for s in SCREENER_STRATEGIES]


def get_strategy(strategy_id: str) -> Dict[str, Any]:
    """按 id 取内置策略；不存在抛 StrategyError"""
    for s in SCREENER_STRATEGIES:
        if s["id"] == strategy_id:
            return json.loads(json.dumps(s))
    raise StrategyError(f"未知策略 id: {strategy_id}")


# ── 校验 ──────────────────────────────────────────────────────

def validate_strategy(s: Dict[str, Any]) -> None:
    """校验策略结构：因子必须存在于 FACTOR_REGISTRY，数值范围合法。

    不通过抛 StrategyError（中文友好消息）。
    """
    if not isinstance(s, dict):
        raise StrategyError("策略必须是 JSON 对象")
    if not s.get("name") or not str(s["name"]).strip():
        raise StrategyError("策略缺少名字（name）")
    filters = s.get("filters")
    if not isinstance(filters, list) or not filters:
        raise StrategyError("策略至少需要一个筛选条件（filters）")
    seen = set()
    for f in filters:
        factor = f.get("factor")
        if factor not in SCREENABLE_FIELDS:
            raise StrategyError(f"未知因子: {factor}（可用: {', '.join(sorted(SCREENABLE_FIELDS))}）")
        if factor in seen:
            raise StrategyError(f"因子 {factor} 重复出现")
        seen.add(factor)
        for key in ("min", "max"):
            val = f.get(key)
            if val is not None:
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    raise StrategyError(f"因子 {factor} 的 {key} 必须是数字")
                if not (val == val):  # NaN
                    raise StrategyError(f"因子 {factor} 的 {key} 不是合法数字")
        lo, hi = f.get("min"), f.get("max")
        if lo is not None and hi is not None and lo > hi:
            raise StrategyError(f"因子 {factor} 的 min({lo}) 大于 max({hi})")
    rank_by = s.get("rank_by")
    if rank_by is not None and rank_by not in SCREENABLE_FIELDS:
        raise StrategyError(f"排名因子未知: {rank_by}")
    top_n = s.get("top_n", 20)
    if not isinstance(top_n, int) or isinstance(top_n, bool) or not 1 <= top_n <= 200:
        raise StrategyError(f"top_n 必须是 1~200 的整数，收到: {top_n}")


def _attach_explains(s: Dict[str, Any]) -> Dict[str, Any]:
    """给策略的每个条件附上白话解释（缺 explain 时从 FACTOR_EXPLAINERS 兜底）"""
    explains = dict(s.get("explains") or {})
    for f in s.get("filters", []):
        factor = f["factor"]
        if factor not in explains:
            meta = FACTOR_EXPLAINERS.get(factor, {})
            explains[factor] = meta.get("desc", "")
    out = dict(s)
    out["explains"] = explains
    return out


# ── LLM 自然语言 → 策略 ──────────────────────────────────────

_LLM_SYSTEM_PROMPT = """你是 A 股选股策略助手。用户会用大白话描述想要的股票，
请把它翻译成一条可执行的选股策略，只输出一个 JSON 对象，不要输出任何其他文字。

JSON 结构：
{
  "name": "策略名字（10 字以内，大白话，如「便宜又赚钱的好公司」）",
  "tagline": "一句话说明这策略适合谁（20 字以内）",
  "filters": [{"factor": "因子名", "min": 数值或省略, "max": 数值或省略}],
  "rank_by": "排名因子（可选，省略则默认 pe_ttm）",
  "top_n": 返回股票数（10~50 的整数）,
  "why": "为什么这样选（1~2 句话）"
}

可用因子（名: 含义 / 单位）：
pe_ttm: 市盈率，越小越便宜 / 倍（合理区间 0~60）
pb: 市净率，越小越便宜 / 倍（合理区间 0~10）
ps_ttm: 市销率，越小越便宜 / 倍
roe: 净资产收益率，越大越好 / 百分比（合理区间 5~30）
roa: 总资产收益率，越大越好 / 百分比
revenue_yoy: 营收同比增速，越大越好 / 百分比
profit_yoy: 净利润同比增速，越大越好 / 百分比
gross_margin: 毛利率，越大越好 / 百分比（合理区间 10~80）
net_margin: 净利率，越大越好 / 百分比
debt_ratio: 资产负债率，越小越稳健 / 百分比（合理区间 10~80）
turnover_rate: 换手率，过高表示炒作 / 百分比（合理区间 0~20）
momentum_20d: 20 日动量，正数=近期上涨 / 小数（0.1 = 涨10%）
momentum_60d: 60 日动量 / 小数
hist_vol_20d: 历史波动率，越小越稳 / 小数
market_cap: 总市值，越大越稳 / 亿元（合理区间 50~10000）

约束：
1. 只使用上面列出的因子名，单位务必按上面的约定（百分比因子写 0~100 的数字，倍因子写倍数）。
2. 筛选条件 1~4 个，别太苛刻，否则选不出股票。
3. min/max 至少给一个，两者都给的必须 min < max。
4. rank_by 从上面因子中选一个最能代表该策略核心的。"""


def _call_llm(system: str, user: str) -> Optional[str]:
    """调用 OpenAI 兼容 chat/completions；任何失败返回 None（不抛异常）"""
    if not LLM_API_KEY:
        return None
    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
                "max_tokens": 1200,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            logger.warning("LLM call failed: HTTP %s body=%s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip() if content else None
    except Exception:
        logger.warning("LLM call exception", exc_info=True)
        return None


def _extract_json(text: str) -> dict:
    """从 LLM 回复里提取 JSON 对象（容忍 ```json 围栏与前后废话）"""
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise StrategyError("LLM 回复中没有 JSON 对象")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise StrategyError(f"LLM 返回的 JSON 无法解析: {e}")


def generate_strategy(prompt: str) -> Dict[str, Any]:
    """自然语言 → 结构化选股策略（LLM 生成 + 严格校验）

    Raises:
        StrategyError: 无 LLM Key / LLM 调用失败 / 输出不合法（API 层转 400）
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise StrategyError("请先描述你想要的股票，比如「低估值的高分红股」")
    content = _call_llm(_LLM_SYSTEM_PROMPT, prompt)
    if not content:
        raise StrategyError(
            "AI 生成失败：未配置 LLM_API_KEY 或 LLM 服务不可用。"
            "可以先用内置策略，或在环境变量配置 LLM_API_KEY 后重试。"
        )
    raw = _extract_json(content)
    if "name" not in raw:
        raw["name"] = prompt[:20]
    if "rank_by" not in raw or not raw.get("rank_by"):
        raw["rank_by"] = "pe_ttm"
    if "top_n" not in raw:
        raw["top_n"] = 20
    validate_strategy(raw)
    s = _attach_explains(raw)
    s["id"] = f"ai_{abs(hash(json.dumps(raw, sort_keys=True))) % 10**8:08d}"
    s["llm_generated"] = True
    return s


# ── 策略执行 ──────────────────────────────────────────────────

def _empty_factor_columns() -> set:
    """最新交易日「整列为空」或「表里没有该列」的因子集合（策略会跳过它们）

    注意：动量/波动类因子（momentum_*/hist_vol_20d/atr_pct）不在 daily_metrics
    表里，screen() 本来就会忽略它们，这里也如实标记为跳过。
    """
    from .db import get_quant_db
    db = get_quant_db()
    try:
        row = db.execute("SELECT MAX(trade_date) AS d FROM daily_metrics").fetchone()
        if not row or not row["d"]:
            return set()
        table_cols = {r["name"] for r in db.execute("PRAGMA table_info(daily_metrics)").fetchall()}
        empty = set()
        for f in SCREENABLE_FIELDS:
            if f not in table_cols:
                empty.add(f)
                continue
            n = db.execute(
                f"SELECT COUNT({f}) AS c FROM daily_metrics WHERE trade_date = ?",
                (row["d"],),
            ).fetchone()["c"]
            if n == 0:
                empty.add(f)
    finally:
        db.close()
    return empty


def apply_strategy(strategy: Dict[str, Any]) -> dict:
    """执行策略选股：空列因子自动跳过，复用 factor_service.screen

    防御规则：desc 因子（越小越好，如 PE/PB/负债率）未给 min 时默认 min=0，
    排除负值（亏损股/资不抵债）——否则「深度低估」会把负 PE 的亏损股排最前。

    Returns:
        factor_service.screen 的返回 dict + skipped_factors（跳过的因子与原因）
        + applied_filters（实际生效的筛选条件，含防御默认值）
    """
    from .factor_service import screen

    skipped = _empty_factor_columns()
    filters = []
    skipped_factors = []
    for f in strategy.get("filters", []):
        if f["factor"] in skipped:
            skipped_factors.append(f["factor"])
            continue
        cond = {k: v for k, v in f.items() if k in ("factor", "min", "max")}
        if FACTOR_REGISTRY.get(f["factor"], {}).get("direction") == "desc" and "min" not in cond:
            cond["min"] = 0
        filters.append(cond)

    result = screen(
        filters=filters,
        rank_by=strategy.get("rank_by"),
        top_n=strategy.get("top_n", 20),
    )
    result["skipped_factors"] = skipped_factors
    result["applied_filters"] = filters
    return result


def llm_configured() -> bool:
    return bool(LLM_API_KEY)
