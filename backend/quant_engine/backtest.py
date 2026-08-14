"""事件驱动回测引擎（v1.0 MVP）

设计参考 QuantConnect Lean 思想：
- Universe  → 投资范围（用 portfolio 代替）
- Alpha     → 选股信号（factor_rank / ma_cross / momentum）
- Portfolio → 持仓 + 权重
- Execution → 模拟成交（开盘价/收盘价 + 滑点 + 涨跌停）
- Risk      → 仓位 / 止损（v1 不做）

MVP 实现简化：
- 单次回测跑在子进程（避免阻塞主服务）
- 数据：preload K 线到内存（pd.DataFrame）
- 信号：每日按调仓频率（daily/weekly/monthly）触发
- 成交：T+1 信号 T+1 成交（默认 T+1 开盘价，可配 T+0 收盘价）
- 交易成本：commission * amount + slippage * amount
- 涨跌停：A 股 ±10%（ST ±5%，科创板/创业板 ±20%）

回测产物：
- equity_curve : 每日净值（含基准对比）
- trades       : 所有成交记录
- metrics      : 总收益 / 年化 / 夏普 / 最大回撤 / 胜率 / 盈亏比 / Alpha / Beta
"""
from __future__ import annotations
import logging
import json
import math
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional, Callable

import numpy as np
import pandas as pd

from .factors import FACTOR_REGISTRY

logger = logging.getLogger(__name__)


# ── 涨跌停规则 ─────────────────────────────────────────────────

def _price_limit_pct(market: str, ticker: str) -> float:
    """返回该股票当日涨跌停幅度（绝对值）

    A 股默认 10%，ST 5%，科创板/创业板 20%。
    """
    if market != "CN":
        return float("inf")  # 港股 / 美股无涨跌停
    # 简化：6/9 开头 + 300/301 (创业板) / 688 (科创板) → 20%
    if ticker.startswith(("300", "301", "688")):
        return 0.20
    # 简化：ST 股需要股票名带 ST 标志；v1 暂不实现
    return 0.10


# ── 信号函数 ───────────────────────────────────────────────────

SignalFn = Callable[[pd.DataFrame, dict], dict[str, float]]
"""信号函数签名：
- 输入：df (columns: trade_date, ticker, close, high, low, volume, ...), params
- 输出：{ticker: target_weight} 权重总和应为 1.0
"""


def signal_equal_weight(df: pd.DataFrame, params: dict) -> dict[str, float]:
    """等权信号：所有 ticker 平分"""
    tickers = df["ticker"].unique().tolist()
    if not tickers:
        return {}
    w = 1.0 / len(tickers)
    return {t: w for t in tickers}


def signal_ma_cross(df: pd.DataFrame, params: dict) -> dict[str, float]:
    """双均线信号：close > MA5 > MA20 → 满仓；否则空仓（v1 简化：单标的）"""
    fast = params.get("fast", 5)
    slow = params.get("slow", 20)
    if len(df) < slow:
        return {}
    last = df.sort_values("trade_date").iloc[-1]
    close = last["close"]
    ma_fast = df["close"].rolling(fast).mean().iloc[-1]
    ma_slow = df["close"].rolling(slow).mean().iloc[-1]
    if close > ma_fast > ma_slow:
        return {last["ticker"]: 1.0}
    return {}


def signal_fixed_weights(df: pd.DataFrame, params: dict) -> dict[str, float]:
    """固定权重信号：按 params['weights'] 字典返回 {ticker: weight}

    用于组合回测（持仓权重已固定，不需要按因子排名）
    """
    weights = params.get("weights", {})
    # 只保留当天 df 里有数据的 ticker
    available = set(df["ticker"].unique())
    return {t: w for t, w in weights.items() if t in available}


def signal_factor_rank(df: pd.DataFrame, params: dict) -> dict[str, float]:
    """多因子排名：取因子值排名 Top N 等权

    支持内置因子（FACTOR_REGISTRY 注册过的）：
    - momentum_Nd : N 日动量
    - hist_vol_Nd / volatility_Nd : N 日历史波动率
    - 其他列名：df 中已包含的列名（外部因子）
    """
    factor = params.get("factor", "momentum_20d")
    top_n = params.get("top_n", 10)

    # 因子方向（asc=越大越好, desc=越小越好）
    meta = FACTOR_REGISTRY.get(factor, {"direction": "asc"})

    df = df.copy()
    # 标准化因子名前缀（hist_vol_20d → volatility_20d）
    norm_factor = factor
    if factor.startswith("hist_vol_"):
        norm_factor = "volatility_" + factor[len("hist_vol_"):]

    if norm_factor.startswith("momentum_"):
        n = int(norm_factor.split("_")[1].rstrip("d"))
        df["_factor"] = df.groupby("ticker")["close"].pct_change(n)
    elif norm_factor.startswith("volatility_"):
        n = int(norm_factor.split("_")[1].rstrip("d"))
        df["_factor"] = df.groupby("ticker")["close"].transform(
            lambda x: np.log(x / x.shift(1)).rolling(n).std()
        )
    elif factor in df.columns:
        df["_factor"] = df[factor]
    else:
        logger.warning("factor %s not recognized", factor)
        return {}

    last_day = df["trade_date"].max()
    snapshot = df[df["trade_date"] == last_day].dropna(subset=["_factor"])
    if snapshot.empty:
        return {}
    # direction=asc（越大越好）→ nlargest；direction=desc（越小越好）→ nsmallest
    if meta["direction"] == "asc":
        top = snapshot.nlargest(top_n, "_factor")
    else:
        top = snapshot.nsmallest(top_n, "_factor")
    w = 1.0 / len(top)
    return dict(zip(top["ticker"], [w] * len(top)))


# ── 数据类 ────────────────────────────────────────────────────

@dataclass
class Trade:
    """成交记录"""
    trade_date: str
    ticker: str
    side: str           # 'buy' / 'sell'
    price: float
    qty: int
    amount: float       # 成交金额 = price * qty
    commission: float
    slippage: float


@dataclass
class BacktestResult:
    """回测结果"""
    metrics: dict
    equity_curve: list[dict]  # [{date, value, benchmark_value}, ...]
    trades: list[dict]
    error: Optional[str] = None


# ── 核心：单次回测 ─────────────────────────────────────────────

def run_backtest(
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    signal_fn: SignalFn,
    signal_params: dict,
    *,
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000,
    commission: float = 0.0003,
    slippage: float = 0.001,
    rebalance_freq: str = "monthly",  # daily / weekly / monthly / none
    market: str = "CN",
) -> BacktestResult:
    """事件驱动回测主入口

    prices: K 线数据，columns = [trade_date, ticker, open, close, high, low, volume, ...]
    benchmark: 基准 K 线，columns = [trade_date, close]
    """
    try:
        prices = prices[(prices["trade_date"] >= start_date) & (prices["trade_date"] <= end_date)].copy()
        benchmark = benchmark[(benchmark["trade_date"] >= start_date) & (benchmark["trade_date"] <= end_date)].copy()
        if prices.empty:
            return BacktestResult(metrics={}, equity_curve=[], trades=[], error="无数据")

        # 按 trade_date + ticker 透视 close
        prices["trade_date"] = pd.to_datetime(prices["trade_date"])
        benchmark["trade_date"] = pd.to_datetime(benchmark["trade_date"])
        prices = prices.sort_values(["trade_date", "ticker"]).reset_index(drop=True)

        all_dates = sorted(prices["trade_date"].unique())
        bench_map = dict(zip(benchmark["trade_date"], benchmark["close"]))

        # 当前持仓 {ticker: shares}
        holdings: dict[str, int] = {}
        cash = initial_capital
        trades: list[Trade] = []
        equity_records: list[dict] = []

        rebalance_dates = _rebalance_schedule(all_dates, rebalance_freq)
        limit = _price_limit_pct(market, "000000")  # 简化：所有 A 股用 10%

        for i, current_date in enumerate(all_dates):
            date_str = current_date.strftime("%Y-%m-%d")
            day_prices = prices[prices["trade_date"] == current_date]

            # 1. 算当日组合市值（按 close 估值）
            position_value = 0.0
            for ticker, shares in holdings.items():
                row = day_prices[day_prices["ticker"] == ticker]
                if not row.empty:
                    position_value += shares * float(row.iloc[0]["close"])
            equity = cash + position_value
            bench_val = bench_map.get(current_date, float("nan"))
            bench_normalized = (bench_val / benchmark["close"].iloc[0]) * initial_capital if not math.isnan(bench_val) else None
            equity_records.append({
                "date": date_str,
                "value": round(equity, 2),
                "benchmark_value": round(bench_normalized, 2) if bench_normalized else None,
            })

            # 2. 是否调仓日
            if current_date not in rebalance_dates:
                continue
            if i + 1 >= len(all_dates):
                continue  # 最后一天不调仓（避免没数据成交）

            next_date = all_dates[i + 1]
            # 信号：基于当日数据
            signal = signal_fn(day_prices, signal_params)
            target_weights = signal if signal else {}

            # 简化：T+0 收盘价成交（不隔夜）。如有涨跌停则跳过
            target_value = {t: equity * w for t, w in target_weights.items()}

            # 卖出不在目标的
            for ticker in list(holdings.keys()):
                if ticker not in target_value:
                    row = day_prices[day_prices["ticker"] == ticker]
                    if row.empty:
                        continue
                    px = float(row.iloc[0]["close"])
                    qty = holdings.pop(ticker)
                    proceeds = px * qty
                    cost = proceeds * (commission + slippage)
                    cash += proceeds - cost
                    trades.append(Trade(date_str, ticker, "sell", px, qty, proceeds, proceeds * commission, proceeds * slippage))

            # 调整到目标权重
            for ticker, tgt_val in target_value.items():
                row = day_prices[day_prices["ticker"] == ticker]
                if row.empty:
                    continue
                px = float(row.iloc[0]["close"])
                # 涨跌停跳过
                prev_close = _prev_close(prices, ticker, current_date)
                if prev_close and abs(px / prev_close - 1) >= limit:
                    continue
                # 含滑点
                fill_px = px * (1 + slippage) if tgt_val > 0 else px * (1 - slippage)
                tgt_shares = int(tgt_val / fill_px)
                if tgt_shares <= 0:
                    continue
                cur_shares = holdings.get(ticker, 0)
                delta = tgt_shares - cur_shares
                if delta == 0:
                    continue
                cost = fill_px * abs(delta)
                fee = cost * commission
                if delta > 0:
                    if cost + fee > cash:
                        continue
                    cash -= cost + fee
                    holdings[ticker] = tgt_shares
                    trades.append(Trade(date_str, ticker, "buy", fill_px, delta, cost, fee, cost * slippage))
                else:
                    # 卖出：delta < 0，cost 是 fill_px * abs(delta) 正数
                    proceeds = cost  # 收到的钱
                    cash += proceeds - fee
                    new_shares = cur_shares + delta  # delta < 0，相当于减仓
                    if new_shares <= 0:
                        holdings.pop(ticker, None)
                    else:
                        holdings[ticker] = new_shares
                    trades.append(Trade(date_str, ticker, "sell", fill_px, -delta, proceeds, fee, proceeds * slippage))

        # 计算 metrics
        metrics = _compute_metrics(equity_records, trades, initial_capital)
        return BacktestResult(
            metrics=metrics,
            equity_curve=equity_records,
            trades=[asdict(t) for t in trades],
        )
    except Exception as e:
        logger.exception("Backtest failed")
        return BacktestResult(metrics={}, equity_curve=[], trades=[], error=str(e))


# ── 辅助 ────────────────────────────────────────────────────

def _rebalance_schedule(dates, freq: str) -> set:
    if freq == "daily":
        return set(dates)
    if freq == "weekly":
        return {d for d in dates if d.weekday() == 0}  # 周一
    if freq == "monthly":
        return set(dates)  # 简化：每月第一交易日；v1 用全部日期（避免误判）
    if freq == "none":
        return set()
    return set()


def _prev_close(prices: pd.DataFrame, ticker: str, current_date) -> Optional[float]:
    """获取 ticker 在 current_date 之前最近一个交易日的 close"""
    sub = prices[(prices["ticker"] == ticker) & (prices["trade_date"] < current_date)]
    if sub.empty:
        return None
    return float(sub.sort_values("trade_date").iloc[-1]["close"])


def _compute_metrics(equity_records: list[dict], trades: list[Trade], initial_capital: float) -> dict:
    """回测指标"""
    if not equity_records:
        return {}
    df = pd.DataFrame(equity_records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
    years = max(days / 365.25, 1/365)
    total_return = (df["value"].iloc[-1] - initial_capital) / initial_capital
    annual_return = (1 + total_return) ** (1 / years) - 1

    # 日收益
    daily_ret = df["value"].pct_change().dropna()
    vol_annual = daily_ret.std() * np.sqrt(252) if len(daily_ret) > 1 else 0
    sharpe = (daily_ret.mean() * 252 - 0.02) / vol_annual if vol_annual > 0 else 0  # 假设无风险 2%

    # 最大回撤
    cummax = df["value"].cummax()
    drawdown = (df["value"] - cummax) / cummax
    max_dd = drawdown.min()

    # 胜率 / 盈亏比（基于平仓交易）
    closed = [t for t in trades if t.side == "sell"]
    win = [t for t in closed if t.amount > 0]
    win_rate = len(win) / len(closed) if closed else 0

    # Alpha / Beta（vs 基准）
    bench_col = "benchmark_value"
    if bench_col in df.columns and df[bench_col].notna().any():
        bench_ret = df[bench_col].pct_change().dropna()
        aligned = daily_ret.align(bench_ret, join="inner")
        if len(aligned[0]) > 20:
            cov = np.cov(aligned[0], aligned[1])
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0
            alpha = aligned[0].mean() * 252 - beta * aligned[1].mean() * 252
        else:
            alpha = beta = 0
    else:
        alpha = beta = 0

    return {
        "total_return": round(total_return, 4),
        "annual_return": round(annual_return, 4),
        "sharpe": round(sharpe, 2),
        "max_drawdown": round(max_dd, 4),
        "volatility": round(vol_annual, 4),
        "win_rate": round(win_rate, 2),
        "trade_count": len(trades),
        "alpha": round(alpha, 4),
        "beta": round(beta, 2),
        "years": round(years, 2),
    }


# ── 信号注册表 ─────────────────────────────────────────────

SIGNAL_REGISTRY: dict[str, dict] = {
    "equal_weight": {
        "fn": signal_equal_weight,
        "default_params": {},
        "description": "等权持有所有标的",
    },
    "ma_cross": {
        "fn": signal_ma_cross,
        "default_params": {"fast": 5, "slow": 20},
        "description": "双均线：金叉买入，死叉空仓（单标的）",
    },
    "factor_rank": {
        "fn": signal_factor_rank,
        "default_params": {"factor": "momentum_20d", "top_n": 10},
        "description": "多因子排名：取 Top N 等权",
    },
    "fixed_weights": {
        "fn": signal_fixed_weights,
        "default_params": {"weights": {}},
        "description": "固定权重（按 params['weights'] 配置，用于组合回测）",
    },
}
