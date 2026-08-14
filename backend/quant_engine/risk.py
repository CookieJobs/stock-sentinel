"""风险指标（v1.0 MVP）

- sharpe: 夏普比率
- sortino: 索提诺比率（仅下行波动）
- calmar: 卡玛比率（年化收益 / 最大回撤绝对值）
- max_drawdown: 最大回撤
- volatility: 年化波动率
- var: 95% VaR（在险价值）
- cvar: 95% CVaR（条件在险价值）
- alpha, beta: 相对基准
- information_ratio: 信息比率
- win_rate: 胜率
- profit_loss_ratio: 盈亏比

输入：equity_curve (list of {date, value, benchmark_value?}) + 初始资金
输出：dict 指标
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from typing import Optional


def compute_all(equity_curve: list[dict], initial_capital: float = 1_000_000,
                risk_free_rate: float = 0.02) -> dict:
    """一站式计算所有风险指标

    equity_curve: [{date, value, benchmark_value?}, ...]
    """
    if not equity_curve:
        return {}
    df = pd.DataFrame(equity_curve)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    if len(df) < 2:
        return {}

    days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
    years = max(days / 365.25, 1/365)

    total_return = (df["value"].iloc[-1] - initial_capital) / initial_capital
    annual_return = (1 + total_return) ** (1 / years) - 1

    daily_ret = df["value"].pct_change().dropna()
    vol_annual = daily_ret.std() * np.sqrt(252) if len(daily_ret) > 1 else 0
    sharpe = ((daily_ret.mean() * 252) - risk_free_rate) / vol_annual if vol_annual > 0 else 0

    downside = daily_ret[daily_ret < 0]
    downside_vol = downside.std() * np.sqrt(252) if len(downside) > 1 else 0
    sortino = ((daily_ret.mean() * 252) - risk_free_rate) / downside_vol if downside_vol > 0 else 0

    cummax = df["value"].cummax()
    drawdown = (df["value"] - cummax) / cummax
    max_dd = drawdown.min()
    calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

    var_95 = daily_ret.quantile(0.05) if len(daily_ret) > 1 else 0
    cvar_95 = daily_ret[daily_ret <= var_95].mean() if (daily_ret <= var_95).any() else 0

    out = {
        "total_return": round(total_return, 4),
        "annual_return": round(annual_return, 4),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "calmar": round(calmar, 2),
        "max_drawdown": round(max_dd, 4),
        "volatility": round(vol_annual, 4),
        "var_95": round(var_95, 4),
        "cvar_95": round(cvar_95, 4),
        "years": round(years, 2),
        "trading_days": len(df),
    }

    # 基准相关指标
    if "benchmark_value" in df.columns and df["benchmark_value"].notna().any():
        bench_ret = df["benchmark_value"].pct_change().dropna()
        aligned = daily_ret.align(bench_ret, join="inner")
        if len(aligned[0]) > 20:
            cov = np.cov(aligned[0], aligned[1])
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0
            alpha = aligned[0].mean() * 252 - beta * aligned[1].mean() * 252
            tracking_error = (aligned[0] - aligned[1]).std() * np.sqrt(252)
            info_ratio = (aligned[0] - aligned[1]).mean() * 252 / tracking_error if tracking_error > 0 else 0
            out.update({
                "alpha": round(alpha, 4),
                "beta": round(beta, 2),
                "tracking_error": round(tracking_error, 4),
                "information_ratio": round(info_ratio, 2),
            })

    return out


def compute_trade_stats(trades: list[dict]) -> dict:
    """基于交易记录算胜率/盈亏比/换手"""
    if not trades:
        return {}
    sell_trades = [t for t in trades if t["side"] == "sell"]
    if not sell_trades:
        return {"trade_count": len(trades), "sell_count": 0}
    # v1 简化：每笔 sell 的 amount 视为盈亏
    pnls = [t["amount"] - t["amount"] * (t.get("commission", 0) / max(t["amount"], 1) * 2) for t in sell_trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = len(wins) / len(pnls) if pnls else 0
    avg_win = np.mean(wins) if wins else 0
    avg_loss = abs(np.mean(losses)) if losses else 0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    return {
        "trade_count": len(trades),
        "sell_count": len(sell_trades),
        "win_rate": round(win_rate, 2),
        "avg_win": round(float(avg_win), 2),
        "avg_loss": round(float(avg_loss), 2),
        "profit_loss_ratio": round(profit_loss_ratio, 2),
    }


# ── 基准映射 ─────────────────────────────────────────────────

BENCHMARKS = {
    # A 股
    "000300.SH": "沪深 300",
    "000905.SH": "中证 500",
    "000852.SH": "中证 1000",
    "000016.SH": "上证 50",
    "399006.SZ": "创业板指",
    # 港股
    "HSI":       "恒生指数",
    # 美股
    "SPX":       "标普 500",
    "NDX":       "纳斯达克 100",
    "DJI":       "道琼斯",
}


def list_benchmarks() -> list[dict]:
    return [{"code": code, "name": name} for code, name in BENCHMARKS.items()]
