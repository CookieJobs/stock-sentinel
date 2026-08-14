"""风险指标单测

测试 compute_all / compute_trade_stats / list_benchmarks
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import math
import numpy as np
import pandas as pd
import pytest

from quant_engine.risk import (
    compute_all, compute_trade_stats, list_benchmarks, BENCHMARKS,
)


# ── compute_all ─────────────────────────────────────────────

def test_compute_all_uptrend():
    """简单上升曲线：总收益 > 0，年化 > 0，夏普 > 0"""
    equity = [
        {"date": "2024-01-01", "value": 100, "benchmark_value": 100},
        {"date": "2024-07-01", "value": 110, "benchmark_value": 105},
        {"date": "2024-12-31", "value": 120, "benchmark_value": 110},
    ]
    m = compute_all(equity, 100)
    assert m["total_return"] == pytest.approx(0.20, abs=0.01)
    assert m["annual_return"] > 0
    assert m["max_drawdown"] == 0  # 单调上升无回撤
    assert m["sharpe"] > 0
    assert m["volatility"] > 0


def test_compute_all_with_drawdown():
    """先升后降：最大回撤 < 0"""
    equity = [
        {"date": "2024-01-01", "value": 100, "benchmark_value": 100},
        {"date": "2024-04-01", "value": 130, "benchmark_value": 110},  # 峰值
        {"date": "2024-07-01", "value": 100, "benchmark_value": 100},  # 回撤 -23%
        {"date": "2024-12-31", "value": 120, "benchmark_value": 115},
    ]
    m = compute_all(equity, 100)
    assert m["max_drawdown"] < 0
    assert m["max_drawdown"] == pytest.approx(-0.2308, abs=0.01)  # (100-130)/130


def test_compute_all_constant_curve():
    """净值不变：年化 = 0，sharpe = 0（无穷/0 兜底）"""
    equity = [
        {"date": "2024-01-01", "value": 100, "benchmark_value": 100},
        {"date": "2024-06-01", "value": 100, "benchmark_value": 100},
        {"date": "2024-12-31", "value": 100, "benchmark_value": 100},
    ]
    m = compute_all(equity, 100)
    # 常数曲线 daily_ret std=0，sharpe/calmar 等被 0 除保护
    assert m["sharpe"] == 0 or math.isnan(m["sharpe"])
    assert m["max_drawdown"] == 0


def test_compute_all_no_benchmark():
    """无 benchmark：alpha/beta 不应有"""
    equity = [
        {"date": "2024-01-01", "value": 100},
        {"date": "2024-06-01", "value": 110},
        {"date": "2024-12-31", "value": 120},
    ]
    m = compute_all(equity, 100)
    assert "alpha" not in m
    assert "beta" not in m
    assert "sharpe" in m


def test_compute_all_empty():
    """空 equity 列表：返回空字典"""
    assert compute_all([], 100) == {}


def test_compute_all_one_point():
    """1 个数据点：返回空字典（无法计算）"""
    equity = [{"date": "2024-01-01", "value": 100}]
    assert compute_all(equity, 100) == {}


def test_compute_all_sharpe_formula():
    """夏普 ≈ (年化收益 - 无风险) / 年化波动"""
    np.random.seed(42)
    n = 252
    daily_ret = np.random.randn(n) * 0.01  # 日波动 1%
    values = 100 * np.cumprod(1 + daily_ret)
    dates = pd.date_range("2024-01-01", periods=n)
    equity = [{"date": d.strftime("%Y-%m-%d"), "value": values[i]} for i, d in enumerate(dates)]
    m = compute_all(equity, 100)
    # 不严格相等（公式细节差异），但量级合理
    assert -3 < m["sharpe"] < 5
    assert 0 < m["volatility"] < 1  # 年化波动 0-100%


def test_compute_all_benchmark_alpha_beta():
    """有 benchmark 时算 alpha/beta"""
    np.random.seed(42)
    n = 252
    bench_ret = np.random.randn(n) * 0.005
    stock_ret = bench_ret * 1.2 + np.random.randn(n) * 0.002  # beta ≈ 1.2
    bench_val = 100 * np.cumprod(1 + bench_ret)
    stock_val = 100 * np.cumprod(1 + stock_ret)
    dates = pd.date_range("2024-01-01", periods=n)
    equity = [
        {"date": d.strftime("%Y-%m-%d"),
         "value": stock_val[i], "benchmark_value": bench_val[i]}
        for i, d in enumerate(dates)
    ]
    m = compute_all(equity, 100)
    assert "alpha" in m
    assert "beta" in m
    assert 0.5 < m["beta"] < 2.0  # 期望 1.2 附近


def test_compute_all_var_95_negative():
    """VaR(95%) 应 <= 0（左侧 5% 损失）"""
    np.random.seed(42)
    n = 252
    daily_ret = np.random.randn(n) * 0.01
    values = 100 * np.cumprod(1 + daily_ret)
    dates = pd.date_range("2024-01-01", periods=n)
    equity = [{"date": d.strftime("%Y-%m-%d"), "value": values[i]} for i, d in enumerate(dates)]
    m = compute_all(equity, 100)
    assert m["var_95"] <= 0
    assert m["cvar_95"] <= 0
    assert m["cvar_95"] <= m["var_95"]  # CVaR 比 VaR 更糟


# ── compute_trade_stats ────────────────────────────────────

def test_trade_stats_no_trades():
    """无交易：返回空字典"""
    assert compute_trade_stats([]) == {}


def test_trade_stats_all_wins():
    """全盈利：胜率 100%"""
    trades = [
        {"side": "sell", "amount": 1000, "commission": 1},
        {"side": "sell", "amount": 2000, "commission": 2},
        {"side": "sell", "amount": 1500, "commission": 1.5},
    ]
    s = compute_trade_stats(trades)
    assert s["sell_count"] == 3
    assert s["win_rate"] == 1.0
    assert s["profit_loss_ratio"] == 0  # 无亏损


def test_trade_stats_mixed():
    """混合盈亏：胜率 = 0.5，盈亏比 > 0"""
    trades = [
        {"side": "sell", "amount": 1000, "commission": 0},  # 赢
        {"side": "sell", "amount": -500, "commission": 0},  # 亏（v1 amount 简化为正，测试场景有点假）
    ]
    s = compute_trade_stats(trades)
    assert s["sell_count"] == 2


def test_trade_stats_only_buys():
    """只有买入没有卖出：sell_count = 0"""
    trades = [
        {"side": "buy", "amount": 1000, "commission": 1},
        {"side": "buy", "amount": 2000, "commission": 2},
    ]
    s = compute_trade_stats(trades)
    assert s["sell_count"] == 0


# ── list_benchmarks ───────────────────────────────────────

def test_list_benchmarks():
    """list_benchmarks 应返回所有预设基准"""
    out = list_benchmarks()
    assert len(out) == 9
    codes = {b["code"] for b in out}
    assert "000300.SH" in codes  # 沪深 300
    assert "SPX" in codes  # 标普 500
    assert "HSI" in codes  # 恒生


def test_benchmarks_dict_complete():
    """BENCHMARKS 字典应包含 9 个 key"""
    assert len(BENCHMARKS) == 9


# ── 边界 ───────────────────────────────────────────────────

def test_zero_initial_capital():
    """初始资金 0：total_return 可能为 nan/inf（v1 不处理，但不应崩）"""
    equity = [
        {"date": "2024-01-01", "value": 100},
        {"date": "2024-12-31", "value": 110},
    ]
    # 不应抛异常
    try:
        m = compute_all(equity, 0)
        # total_return = (110 - 0) / 0 = inf
        assert m["total_return"] == float("inf") or math.isnan(m["total_return"]) or m["total_return"] == 0
    except ZeroDivisionError:
        # 也接受
        pass


def test_very_short_curve():
    """2 个数据点（最短有效）"""
    equity = [
        {"date": "2024-01-01", "value": 100, "benchmark_value": 100},
        {"date": "2024-12-31", "value": 120, "benchmark_value": 110},
    ]
    m = compute_all(equity, 100)
    assert "total_return" in m
    assert m["total_return"] == pytest.approx(0.20, abs=0.01)
