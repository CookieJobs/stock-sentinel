"""组合服务 — Portfolio 完整化

- valuation(): 组合估值（实时价 × 持仓权重 → 总市值 + 各项占比）
- rebalance_signal(): 生成再平衡操作建议（buy/sell 哪些 + 多少）
- backtest_payload(): 把组合转成回测所需的 tickers + weights
- signal_fixed_weights(): 固定权重信号（给 backtest 引擎用）
"""
from __future__ import annotations
import logging
from typing import Optional

import pandas as pd

from .db import get_quant_db
from .portfolio import get_portfolio
from .kline_service import get_or_fetch

logger = logging.getLogger(__name__)


# ── 估值 ──────────────────────────────────────────────────────

def valuation(portfolio_id: int) -> dict:
    """组合估值：拉各持仓最新价 → 算市值 + 权重

    返回：
    {
      portfolio_id, portfolio_name, benchmark,
      total_value, holdings: [{ticker, weight, price, value, pct_of_total}],
      drift: [{ticker, target_weight, current_weight, drift, action}]
    }
    """
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        return {"error": "组合不存在"}
    if not portfolio["holdings"]:
        return {"portfolio_id": portfolio_id, "portfolio_name": portfolio["name"],
                "total_value": 0, "holdings": [], "drift": []}

    # 拉每个 ticker 最新价
    prices = {}
    for h in portfolio["holdings"]:
        try:
            df = get_or_fetch(h["ticker"], h["market"], period="1d", adj="qfq")
            if df is not None and not df.empty:
                prices[h["ticker"]] = float(df.iloc[-1]["close"])
        except Exception as e:
            logger.warning("Failed to get price for %s: %s", h["ticker"], e)

    # 计算每项市值（weight × price 作为占位）
    total = 0.0
    rows = []
    for h in portfolio["holdings"]:
        price = prices.get(h["ticker"])
        # 简化：用 weight × price 反推"伪市值"，用于计算占比
        # 真实场景下：v1 暂不支持"持仓股数"概念，weight 既是目标也是当前
        # v2 引入 cash + 持仓股数
        value = h["weight"] * price if price else 0
        total += value
        rows.append({
            "ticker": h["ticker"],
            "market": h["market"],
            "target_weight": h["weight"],
            "price": price,
            "value": value,
        })

    # 算 current_weight 和 drift
    drift = []
    for r in rows:
        current_weight = r["value"] / total if total > 0 else 0
        diff = current_weight - r["target_weight"]
        drift_val = abs(diff)
        action = "buy" if diff < -0.01 else ("sell" if diff > 0.01 else "hold")
        drift.append({
            "ticker": r["ticker"],
            "target_weight": round(r["target_weight"], 4),
            "current_weight": round(current_weight, 4),
            "drift": round(drift_val, 4),
            "action": action,
        })
        r["pct_of_total"] = round(current_weight, 4)

    return {
        "portfolio_id": portfolio_id,
        "portfolio_name": portfolio["name"],
        "benchmark": portfolio["benchmark"],
        "total_value": round(total, 2),
        "holdings": rows,
        "drift": drift,
    }


# ── 再平衡操作建议 ─────────────────────────────────────────────

def rebalance_actions(portfolio_id: int, total_capital: float = 1_000_000,
                      threshold: float = 0.05) -> list[dict]:
    """基于 valuation 生成再平衡操作（按当前价 + 目标权重 → 应买入/卖出金额）

    Args:
        total_capital: 假设的总资金
        threshold: 偏差超过此值才提示再平衡
    """
    val = valuation(portfolio_id)
    if "error" in val:
        return []
    actions = []
    for d in val["drift"]:
        if d["drift"] < threshold:
            continue
        target_value = total_capital * d["target_weight"]
        current_value = total_capital * d["current_weight"]
        delta = target_value - current_value
        actions.append({
            "ticker": d["ticker"],
            "action": "buy" if delta > 0 else "sell",
            "delta_value": round(delta, 2),
            "delta_pct": round(d["drift"], 4),
            "reason": f"目标 {d['target_weight']*100:.1f}% → 当前 {d['current_weight']*100:.1f}%，偏差 {d['drift']*100:.1f}%",
        })
    return actions


# ── 回测 payload 转换 ─────────────────────────────────────────

def to_backtest_payload(portfolio_id: int, *,
                       strategy: str = "fixed_weights",
                       start_date: str = "2024-01-01",
                       end_date: str = "2024-12-31",
                       initial_capital: float = 1_000_000,
                       benchmark: Optional[str] = None,
                       rebalance_freq: str = "monthly") -> dict:
    """把 portfolio 转成 backtest_service.submit() 需要的 payload"""
    portfolio = get_portfolio(portfolio_id)
    if not portfolio:
        raise ValueError(f"组合不存在: {portfolio_id}")
    if not portfolio["holdings"]:
        raise ValueError("组合为空，无标的")
    return {
        "name": f"{portfolio['name']} 回测",
        "strategy": strategy,
        "params": {"weights": {h["ticker"]: h["weight"] for h in portfolio["holdings"]}},
        "tickers": [h["ticker"] for h in portfolio["holdings"]],
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "benchmark": benchmark or portfolio["benchmark"],
        "rebalance_freq": rebalance_freq,
    }
