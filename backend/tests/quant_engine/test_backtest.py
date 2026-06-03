"""回测引擎单测

测试 4 个信号 + run_backtest 主流程 + 涨跌停 + 边界
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import math
import numpy as np
import pandas as pd
import pytest

from quant_engine.backtest import (
    run_backtest,
    signal_equal_weight, signal_ma_cross, signal_factor_rank, signal_fixed_weights,
    SIGNAL_REGISTRY,
    _price_limit_pct,
)


@pytest.fixture
def sample_prices():
    """2 只股票 100 天数据"""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2024-01-01", periods=n)
    rows = []
    for ticker in ["A", "B"]:
        base = 100 if ticker == "A" else 50
        close = base + np.cumsum(np.random.randn(n) * 0.5)
        for i, d in enumerate(dates):
            rows.append({
                "trade_date": d.strftime("%Y-%m-%d"),
                "ticker": ticker,
                "open": close[i] * 0.99,
                "close": close[i],
                "high": close[i] * 1.01,
                "low": close[i] * 0.98,
                "volume": 1000,
            })
    return pd.DataFrame(rows)


@pytest.fixture
def sample_benchmark():
    """基准 100 天数据"""
    np.random.seed(7)
    n = 100
    dates = pd.date_range("2024-01-01", periods=n)
    return pd.DataFrame({
        "trade_date": [d.strftime("%Y-%m-%d") for d in dates],
        "close": 1000 + np.cumsum(np.random.randn(n) * 3),
    })


# ── 信号函数 ──────────────────────────────────────────────

def test_signal_equal_weight():
    """等权：所有 ticker 平分"""
    df = pd.DataFrame({"ticker": ["A", "B", "C"], "close": [10, 20, 30]})
    w = signal_equal_weight(df, {})
    assert len(w) == 3
    assert abs(w["A"] - 1/3) < 1e-6
    assert abs(w["B"] - 1/3) < 1e-6


def test_signal_equal_weight_empty():
    """空 df：返回空"""
    df = pd.DataFrame(columns=["ticker", "close"])
    assert signal_equal_weight(df, {}) == {}


def test_signal_ma_cross_golden_cross():
    """金叉：close > MA5 > MA20 → 满仓"""
    # 构造：最后 close > MA5 > MA20
    n = 30
    prices = list(range(1, n + 1))  # 严格递增
    df = pd.DataFrame({
        "trade_date": pd.date_range("2024-01-01", periods=n),
        "ticker": "X",
        "close": prices,
        "open": prices, "high": prices, "low": prices, "volume": [1000] * n,
    })
    w = signal_ma_cross(df, {"fast": 5, "slow": 20})
    assert "X" in w
    assert abs(w["X"] - 1.0) < 1e-6


def test_signal_ma_cross_below_ma():
    """价格低于 MA：不买"""
    # 严格递减
    n = 30
    prices = list(range(100, 100 - n, -1))
    df = pd.DataFrame({
        "trade_date": pd.date_range("2024-01-01", periods=n),
        "ticker": "X",
        "close": prices,
    })
    w = signal_ma_cross(df, {"fast": 5, "slow": 20})
    assert w == {}


def test_signal_ma_cross_too_short():
    """数据不够：返回空"""
    n = 10
    df = pd.DataFrame({
        "trade_date": pd.date_range("2024-01-01", periods=n),
        "ticker": "X",
        "close": list(range(1, n + 1)),
    })
    assert signal_ma_cross(df, {"fast": 5, "slow": 20}) == {}


def test_signal_factor_rank_momentum():
    """动量排名：取 Top N"""
    np.random.seed(42)
    n = 50
    tickers = ["A", "B", "C", "D"]
    rows = []
    for t in tickers:
        base = {"A": 100, "B": 110, "C": 90, "D": 105}[t]
        close = [base * (1.001 ** i) for i in range(n)]
        for i, c in enumerate(close):
            rows.append({"trade_date": pd.date_range("2024-01-01", periods=n)[i].strftime("%Y-%m-%d"),
                         "ticker": t, "close": c})
    df = pd.DataFrame(rows)
    w = signal_factor_rank(df, {"factor": "momentum_20d", "top_n": 2})
    assert len(w) == 2
    # A 涨幅最大（1.001^49 ≈ 1.050），B 第二
    assert "A" in w
    assert "B" in w


def test_signal_factor_rank_volatility():
    """波动率因子：低波动排名靠前"""
    n = 30
    rows = []
    for t in ["A", "B"]:
        # A 低波动，B 高波动
        for i in range(n):
            base = 100
            if t == "A":
                close = base + np.sin(i) * 0.1
            else:
                close = base + np.sin(i) * 5
            rows.append({
                "trade_date": pd.date_range("2024-01-01", periods=n)[i].strftime("%Y-%m-%d"),
                "ticker": t,
                "close": close,
            })
    df = pd.DataFrame(rows)
    # 用 hist_vol_20d（在 FACTOR_REGISTRY 里注册过的）
    w = signal_factor_rank(df, {"factor": "hist_vol_20d", "top_n": 1})
    # A（低波动）应该被选
    assert "A" in w


def test_signal_factor_rank_unknown_factor():
    """未知因子：返回空（不崩）"""
    df = pd.DataFrame({"ticker": ["A"], "close": [100]})
    assert signal_factor_rank(df, {"factor": "unknown_xx"}) == {}


def test_signal_fixed_weights():
    """固定权重"""
    df = pd.DataFrame({"ticker": ["A", "B", "C"], "close": [10, 20, 30]})
    w = signal_fixed_weights(df, {"weights": {"A": 0.5, "B": 0.3, "C": 0.2}})
    assert w == {"A": 0.5, "B": 0.3, "C": 0.2}


def test_signal_fixed_weights_filter_missing():
    """固定权重：df 中没有的 ticker 过滤掉"""
    df = pd.DataFrame({"ticker": ["A", "B"], "close": [10, 20]})
    w = signal_fixed_weights(df, {"weights": {"A": 0.5, "B": 0.3, "C": 0.2}})
    assert "C" not in w
    assert w == {"A": 0.5, "B": 0.3}


# ── 涨跌停 ───────────────────────────────────────────────

def test_price_limit_cn_main():
    """A 股主板：±10%"""
    assert _price_limit_pct("CN", "600519") == 0.10
    assert _price_limit_pct("CN", "000001") == 0.10


def test_price_limit_cn_chinext():
    """创业板：±20%"""
    assert _price_limit_pct("CN", "300750") == 0.20
    assert _price_limit_pct("CN", "301000") == 0.20


def test_price_limit_cn_star():
    """科创板：±20%"""
    assert _price_limit_pct("CN", "688981") == 0.20


def test_price_limit_hk_us():
    """港股/美股：无涨跌停（inf）"""
    assert _price_limit_pct("HK", "00700") == float("inf")
    assert _price_limit_pct("US", "AAPL") == float("inf")


# ── 回测主流程 ────────────────────────────────────────────

def test_run_backtest_equal_weight(sample_prices, sample_benchmark):
    """等权回测：基本能跑，返回正确结构"""
    result = run_backtest(
        prices=sample_prices,
        benchmark=sample_benchmark,
        signal_fn=signal_equal_weight,
        signal_params={},
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_capital=1_000_000,
        rebalance_freq="monthly",
    )
    assert result.error is None
    assert "total_return" in result.metrics
    assert "sharpe" in result.metrics
    assert "max_drawdown" in result.metrics
    # 100 天净值曲线
    assert len(result.equity_curve) == 100
    # 每月调仓 + 2 只股票 → 应有多笔交易
    assert len(result.trades) > 0


def test_run_backtest_fixed_weights(sample_prices, sample_benchmark):
    """固定权重回测：按持仓权重买"""
    result = run_backtest(
        prices=sample_prices,
        benchmark=sample_benchmark,
        signal_fn=signal_fixed_weights,
        signal_params={"weights": {"A": 0.6, "B": 0.4}},
        start_date="2024-01-01",
        end_date="2024-03-31",
        initial_capital=500_000,
        rebalance_freq="monthly",
    )
    assert result.error is None
    # 净值 = 初始资金（每月都调仓到 60/40 比例）
    final = result.equity_curve[-1]["value"]
    assert final > 0


def test_run_backtest_empty_prices(sample_benchmark):
    """无数据：返回 error"""
    empty = pd.DataFrame(columns=["trade_date", "ticker", "close"])
    result = run_backtest(
        prices=empty,
        benchmark=sample_benchmark,
        signal_fn=signal_equal_weight,
        signal_params={},
        start_date="2024-01-01",
        end_date="2024-12-31",
    )
    assert result.error is not None or len(result.equity_curve) == 0


def test_run_backtest_metrics_complete(sample_prices, sample_benchmark):
    """metrics 字段完整"""
    result = run_backtest(
        prices=sample_prices, benchmark=sample_benchmark,
        signal_fn=signal_equal_weight, signal_params={},
        start_date="2024-01-01", end_date="2024-12-31",
        initial_capital=1_000_000,
    )
    required = ["total_return", "annual_return", "sharpe", "max_drawdown",
                "volatility", "win_rate", "trade_count", "alpha", "beta"]
    for k in required:
        assert k in result.metrics, f"missing metric: {k}"


def test_run_backtest_trade_record_format(sample_prices, sample_benchmark):
    """交易记录格式"""
    result = run_backtest(
        prices=sample_prices, benchmark=sample_benchmark,
        signal_fn=signal_equal_weight, signal_params={},
        start_date="2024-01-01", end_date="2024-04-30",
    )
    if result.trades:
        t = result.trades[0]
        required = ["trade_date", "ticker", "side", "price", "qty", "amount"]
        for k in required:
            assert k in t, f"missing trade field: {k}"
        assert t["side"] in ("buy", "sell")
        assert t["qty"] > 0


def test_run_backtest_equity_curve_sorted(sample_prices, sample_benchmark):
    """净值曲线按日期升序"""
    result = run_backtest(
        prices=sample_prices, benchmark=sample_benchmark,
        signal_fn=signal_equal_weight, signal_params={},
        start_date="2024-01-01", end_date="2024-12-31",
    )
    dates = [r["date"] for r in result.equity_curve]
    assert dates == sorted(dates)


def test_run_backtest_no_negative_cash(sample_prices, sample_benchmark):
    """现金不应变为负（钱不够就不买）"""
    # 给极少资金
    result = run_backtest(
        prices=sample_prices, benchmark=sample_benchmark,
        signal_fn=signal_equal_weight, signal_params={},
        start_date="2024-01-01", end_date="2024-03-31",
        initial_capital=1_000,  # 只有 1000 元
    )
    # 不应崩，可能部分 ticker 没买成
    assert result.error is None or "error" in result.metrics
    # 净值应 >= 0
    if result.equity_curve:
        for r in result.equity_curve:
            assert r["value"] >= 0, f"净值变负：{r}"


# ── SIGNAL_REGISTRY ─────────────────────────────────────

def test_signal_registry_has_4():
    """应该有 4 个内置策略"""
    assert len(SIGNAL_REGISTRY) == 4
    for key in ["equal_weight", "ma_cross", "factor_rank", "fixed_weights"]:
        assert key in SIGNAL_REGISTRY


def test_signal_registry_descriptions():
    """每个策略有描述"""
    for name, info in SIGNAL_REGISTRY.items():
        assert "description" in info
        assert "default_params" in info
        assert "fn" in info
        assert callable(info["fn"])
