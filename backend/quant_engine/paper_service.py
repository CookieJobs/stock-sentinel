"""模拟交易（Paper Trading）服务 — 组合 / 持仓 / 成交 / 净值

规则（v1 简化）：
- 以真实行情成交（DataFetcher，demo 假数据拒绝交易）
- buy：现金足够即可；sell：不超过持仓；卖出实现盈亏计入 realized_pnl
- 净值 = 现金 + Σ 持仓市值（mark-to-market 时用最新价）
"""
import logging
from datetime import datetime
from typing import Optional

from data_fetcher import DataFetcher as DF
from .db import get_quant_db

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def list_portfolios() -> list:
    db = get_quant_db()
    try:
        rows = db.execute(
            "SELECT p.*, COALESCE(SUM(pp.qty * pp.avg_cost), 0) AS positions_cost "
            "FROM paper_portfolios p "
            "LEFT JOIN paper_positions pp ON pp.portfolio_id = p.id "
            "GROUP BY p.id ORDER BY p.id DESC"
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["positions_cost"] = round(d["positions_cost"], 2)
            out.append(d)
        return out
    finally:
        db.close()


def create_portfolio(name: str, initial_capital: float = 100000.0) -> dict:
    db = get_quant_db()
    try:
        cur = db.execute(
            "INSERT INTO paper_portfolios (name, initial_capital, cash) VALUES (?, ?, ?)",
            (name, initial_capital, initial_capital),
        )
        db.commit()
        return {"id": cur.lastrowid, "name": name, "initial_capital": initial_capital}
    finally:
        db.close()


def close_portfolio(portfolio_id: int) -> bool:
    db = get_quant_db()
    try:
        cur = db.execute(
            "UPDATE paper_portfolios SET status = 'closed' WHERE id = ? AND status = 'active'",
            (portfolio_id,),
        )
        db.commit()
        return cur.rowcount > 0
    finally:
        db.close()


def delete_portfolio(portfolio_id: int) -> bool:
    db = get_quant_db()
    try:
        cur = db.execute("DELETE FROM paper_portfolios WHERE id = ?", (portfolio_id,))
        db.commit()
        return cur.rowcount > 0
    finally:
        db.close()


def _live_price(ticker: str):
    """真实行情价格；demo 假数据返回 None（拒绝交易）"""
    info = DF.get_stock_info(ticker)
    if not info or info.get("source") == "demo":
        return None, None
    return info.get("current_price"), info.get("market")


def trade(portfolio_id: int, ticker: str, side: str, qty: float) -> dict:
    """模拟下单：buy / sell，返回成交摘要"""
    ticker = ticker.strip().upper()
    if side not in ("buy", "sell"):
        raise ValueError("side 必须是 buy / sell")
    if qty <= 0:
        raise ValueError("数量必须大于 0")
    price, market = _live_price(ticker)
    if price is None:
        raise ValueError(f"{ticker} 当前无真实行情（数据源不可用），拒绝模拟成交")

    db = get_quant_db()
    try:
        row = db.execute(
            "SELECT * FROM paper_portfolios WHERE id = ? AND status = 'active'",
            (portfolio_id,),
        ).fetchone()
        if not row:
            raise ValueError("组合不存在或已关闭")
        cash = row["cash"]
        amount = round(price * qty, 2)
        realized_pnl = None

        if side == "buy":
            if amount > cash + 1e-6:
                raise ValueError(f"现金不足：需 {amount:.2f}，可用 {cash:.2f}")
            pos = db.execute(
                "SELECT * FROM paper_positions WHERE portfolio_id = ? AND ticker = ?",
                (portfolio_id, ticker),
            ).fetchone()
            if pos:
                new_qty = pos["qty"] + qty
                new_cost = (pos["avg_cost"] * pos["qty"] + amount) / new_qty
                db.execute(
                    "UPDATE paper_positions SET qty = ?, avg_cost = ? WHERE id = ?",
                    (new_qty, round(new_cost, 4), pos["id"]),
                )
            else:
                db.execute(
                    "INSERT INTO paper_positions (portfolio_id, ticker, market, qty, avg_cost) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (portfolio_id, ticker, market or "CN", qty, round(price, 4)),
                )
            db.execute(
                "UPDATE paper_portfolios SET cash = cash - ? WHERE id = ?", (amount, portfolio_id)
            )
        else:  # sell
            pos = db.execute(
                "SELECT * FROM paper_positions WHERE portfolio_id = ? AND ticker = ?",
                (portfolio_id, ticker),
            ).fetchone()
            if not pos or pos["qty"] < qty - 1e-6:
                raise ValueError(f"持仓不足：{ticker} 持有 {pos['qty'] if pos else 0}")
            realized_pnl = round((price - pos["avg_cost"]) * qty, 2)
            remain = pos["qty"] - qty
            if remain < 1e-6:
                db.execute("DELETE FROM paper_positions WHERE id = ?", (pos["id"],))
            else:
                db.execute(
                    "UPDATE paper_positions SET qty = ? WHERE id = ?", (remain, pos["id"])
                )
            db.execute(
                "UPDATE paper_portfolios SET cash = cash + ? WHERE id = ?", (amount, portfolio_id)
            )

        db.execute(
            """INSERT INTO paper_trades (portfolio_id, trade_date, ticker, side, price, qty, amount, realized_pnl)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (portfolio_id, _now(), ticker, side, round(price, 4), qty, amount, realized_pnl),
        )
        db.commit()
        return {
            "ticker": ticker, "side": side, "price": round(price, 4), "qty": qty,
            "amount": amount, "realized_pnl": realized_pnl,
            "market": market,
        }
    finally:
        db.close()


def _mark_prices(positions: list) -> dict:
    """批量取最新价（逐只调用，量小可接受）"""
    prices = {}
    for p in positions:
        info = DF.get_stock_info(p["ticker"])
        if info and info.get("source") != "demo" and info.get("current_price"):
            prices[p["ticker"]] = info["current_price"]
    return prices


def mark_to_market(portfolio_id: int) -> dict:
    """按最新行情重估持仓并记录当日净值，返回 {equity, cash, positions_value}"""
    db = get_quant_db()
    try:
        row = db.execute(
            "SELECT * FROM paper_portfolios WHERE id = ?", (portfolio_id,)
        ).fetchone()
        if not row:
            raise ValueError("组合不存在")
        positions = [
            dict(r) for r in db.execute(
                "SELECT * FROM paper_positions WHERE portfolio_id = ?", (portfolio_id,)
            ).fetchall()
        ]
    finally:
        db.close()

    prices = _mark_prices(positions)
    positions_value = round(sum(p["qty"] * prices.get(p["ticker"], p["avg_cost"]) for p in positions), 2)
    equity = round(row["cash"] + positions_value, 2)

    db = get_quant_db()
    try:
        db.execute(
            """INSERT OR REPLACE INTO paper_equity
               (portfolio_id, equity_date, equity_value, cash, positions_value)
               VALUES (?, ?, ?, ?, ?)""",
            (portfolio_id, _today(), equity, round(row["cash"], 2), positions_value),
        )
        db.commit()
    finally:
        db.close()
    return {"equity": equity, "cash": round(row["cash"], 2), "positions_value": positions_value}


def get_detail(portfolio_id: int) -> dict:
    """组合详情：持仓（带最新价/浮盈）+ 成交记录 + 净值曲线"""
    db = get_quant_db()
    try:
        row = db.execute(
            "SELECT * FROM paper_portfolios WHERE id = ?", (portfolio_id,)
        ).fetchone()
        if not row:
            return None
        portfolio = dict(row)
        positions = [
            dict(r) for r in db.execute(
                "SELECT * FROM paper_positions WHERE portfolio_id = ?", (portfolio_id,)
            ).fetchall()
        ]
        trades = [
            dict(r) for r in db.execute(
                "SELECT id, trade_date, ticker, side, price, qty, amount, realized_pnl "
                "FROM paper_trades WHERE portfolio_id = ? ORDER BY id DESC LIMIT 100",
                (portfolio_id,),
            ).fetchall()
        ]
        equity = [
            dict(r) for r in db.execute(
                "SELECT equity_date, equity_value FROM paper_equity "
                "WHERE portfolio_id = ? ORDER BY equity_date ASC",
                (portfolio_id,),
            ).fetchall()
        ]
    finally:
        db.close()

    prices = _mark_prices(positions)
    enriched = []
    total_value = portfolio["cash"]
    for p in positions:
        price = prices.get(p["ticker"])
        market_value = round(p["qty"] * (price or p["avg_cost"]), 2)
        pnl = round((price - p["avg_cost"]) * p["qty"], 2) if price else None
        total_value += market_value
        enriched.append({**p, "price": price, "market_value": market_value, "pnl": pnl})

    return {
        "portfolio": portfolio,
        "positions": enriched,
        "trades": trades,
        "equity_curve": equity,
        "total_value": round(total_value, 2),
        "total_pnl": round(total_value - portfolio["initial_capital"], 2),
    }
