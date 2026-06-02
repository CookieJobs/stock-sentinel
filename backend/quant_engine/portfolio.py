"""组合管理（v1.0 MVP）

- CRUD：创建 / 列出 / 删除组合
- 持仓：添加 / 调整权重 / 删除
- 再平衡提醒：监控当前权重 vs 目标权重，偏差 > 阈值时提醒
- 估值：基于当前 K 线算组合市值
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .db import get_quant_db

logger = logging.getLogger(__name__)


# ── CRUD ──────────────────────────────────────────────────────

def create_portfolio(name: str, description: str = "", benchmark: str = "000300.SH",
                    rebalance_freq: str = "monthly") -> int:
    """创建组合，返回 id"""
    db = get_quant_db()
    try:
        cur = db.execute(
            "INSERT INTO portfolios (name, description, benchmark, rebalance_freq) VALUES (?, ?, ?, ?)",
            (name, description, benchmark, rebalance_freq),
        )
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


def list_portfolios() -> list[dict]:
    db = get_quant_db()
    try:
        rows = db.execute("SELECT * FROM portfolios ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def get_portfolio(portfolio_id: int) -> Optional[dict]:
    db = get_quant_db()
    try:
        row = db.execute("SELECT * FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        if not row:
            return None
        portfolio = dict(row)
        holdings = db.execute(
            "SELECT * FROM portfolio_holdings WHERE portfolio_id = ? ORDER BY ticker", (portfolio_id,)
        ).fetchall()
        portfolio["holdings"] = [dict(h) for h in holdings]
        return portfolio
    finally:
        db.close()


def delete_portfolio(portfolio_id: int) -> bool:
    db = get_quant_db()
    try:
        cur = db.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
        db.commit()
        return cur.rowcount > 0
    finally:
        db.close()


def add_holding(portfolio_id: int, ticker: str, market: str = "CN", weight: float = 0.0) -> bool:
    db = get_quant_db()
    try:
        db.execute(
            "INSERT OR REPLACE INTO portfolio_holdings (portfolio_id, ticker, market, weight) VALUES (?, ?, ?, ?)",
            (portfolio_id, ticker.upper(), market, weight),
        )
        db.commit()
        return True
    finally:
        db.close()


def update_holding_weight(portfolio_id: int, ticker: str, weight: float) -> bool:
    db = get_quant_db()
    try:
        cur = db.execute(
            "UPDATE portfolio_holdings SET weight = ? WHERE portfolio_id = ? AND ticker = ?",
            (weight, portfolio_id, ticker.upper()),
        )
        db.commit()
        return cur.rowcount > 0
    finally:
        db.close()


def remove_holding(portfolio_id: int, ticker: str) -> bool:
    db = get_quant_db()
    try:
        cur = db.execute(
            "DELETE FROM portfolio_holdings WHERE portfolio_id = ? AND ticker = ?",
            (portfolio_id, ticker.upper()),
        )
        db.commit()
        return cur.rowcount > 0
    finally:
        db.close()


# ── 再平衡检测 ──────────────────────────────────────────────

def check_rebalance(portfolio_id: int, current_prices: dict[str, float], threshold: float = 0.05) -> dict:
    """检查组合是否需要再平衡

    current_prices: {ticker: current_price}
    threshold: 权重偏差超过此值（如 0.05 = 5%）则提醒
    """
    portfolio = get_portfolio(portfolio_id)
    if not portfolio or not portfolio["holdings"]:
        return {"need_rebalance": False, "details": []}

    # 当前市值
    market_value = {}
    total = 0.0
    for h in portfolio["holdings"]:
        px = current_prices.get(h["ticker"])
        if px is None:
            continue
        # v1 简化：用 weight × 当前 price 反推 shares；首次添加需要传 shares，v1 用 weight 直接对比
        market_value[h["ticker"]] = h["weight"] * px
        total += h["weight"] * px

    # 当前权重
    current_weights = {t: v / total if total > 0 else 0 for t, v in market_value.items()}
    target_weights = {h["ticker"]: h["weight"] for h in portfolio["holdings"]}

    # 偏差
    details = []
    need_rebalance = False
    for ticker, target in target_weights.items():
        current = current_weights.get(ticker, 0)
        diff = abs(current - target)
        if diff > threshold:
            need_rebalance = True
        details.append({
            "ticker": ticker,
            "target_weight": round(target, 4),
            "current_weight": round(current, 4),
            "drift": round(diff, 4),
            "action": "buy" if current < target else "sell",
        })

    return {
        "need_rebalance": need_rebalance,
        "portfolio_id": portfolio_id,
        "portfolio_name": portfolio["name"],
        "total_value": round(total, 2),
        "details": details,
    }
