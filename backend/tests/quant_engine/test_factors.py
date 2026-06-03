"""因子库单测

测试 FACTOR_REGISTRY / list_factors / cross_sectional_rank
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd
import pytest

from quant_engine.factors import (
    FACTOR_REGISTRY,
    list_factors,
    cross_sectional_rank,
    factor_pe_ttm, factor_roe, factor_momentum,
    factor_atr_pct, factor_hist_vol, factor_beta,
)


# ── 注册表 ─────────────────────────────────────────────

def test_registry_count():
    """FACTOR_REGISTRY 应有 15 个因子"""
    assert len(FACTOR_REGISTRY) == 15


def test_registry_categories():
    """5 大类都有"""
    cats = {meta["category"] for meta in FACTOR_REGISTRY.values()}
    assert "估值" in cats
    assert "成长" in cats
    assert "质量" in cats
    assert "动量" in cats
    assert "波动" in cats


def test_registry_direction_field():
    """每个因子都有 direction（asc/desc）"""
    for name, meta in FACTOR_REGISTRY.items():
        assert "direction" in meta, f"{name} missing direction"
        assert meta["direction"] in ("asc", "desc"), f"{name} bad direction"


def test_list_factors_returns_metadata():
    """list_factors 返回结构化"""
    out = list_factors()
    assert len(out) == 15
    for f in out:
        assert {"name", "category", "direction"} <= set(f.keys())


# ── 因子函数 ─────────────────────────────────────────

def test_factor_pe_ttm_identity():
    """pe_ttm = 输入本身"""
    s = pd.Series([10, 20, 30, 40, 50])
    pd.testing.assert_series_equal(factor_pe_ttm(s), s)


def test_factor_roe_identity():
    """roe = 输入本身"""
    s = pd.Series([0.05, 0.10, 0.15, 0.20])
    pd.testing.assert_series_equal(factor_roe(s), s)


def test_factor_momentum_20d():
    """20 日动量"""
    close = pd.Series([100] + [100] * 19 + [110, 121])
    out = factor_momentum(close, period=20)
    # index 21 = (121 - 100) / 100 = 0.21
    assert out.iloc[21] == pytest.approx(0.21, abs=0.01)
    # index 20 = (110 - 100) / 100 = 0.1
    assert out.iloc[20] == pytest.approx(0.10, abs=0.01)
    # 前 20 个值（index 0-19）NaN
    assert out.iloc[:20].isna().all()


def test_factor_momentum_default_20():
    """默认 period=20"""
    close = pd.Series(range(1, 50))
    out_default = factor_momentum(close)
    out_20 = factor_momentum(close, period=20)
    pd.testing.assert_series_equal(out_default, out_20)


def test_factor_hist_vol_positive():
    """历史波动率应 > 0"""
    np.random.seed(42)
    n = 252
    close = pd.Series(100 * np.cumprod(1 + np.random.randn(n) * 0.01))
    vol = factor_hist_vol(close, period=20)
    valid = vol.dropna()
    assert (valid > 0).all()
    # 年化波动率应在 0-1 之间
    assert valid.max() < 2


def test_factor_atr_pct():
    """ATR/close = 波动率归一化"""
    atr = pd.Series([1, 2, 3, 4, 5])
    close = pd.Series([100, 100, 100, 100, 100])
    out = factor_atr_pct(atr, close)
    assert out.iloc[0] == 0.01
    assert out.iloc[4] == 0.05


def test_factor_beta():
    """Beta = cov / var"""
    np.random.seed(42)
    n = 100
    bench = pd.Series(np.cumsum(np.random.randn(n)))
    # stock = 1.5 * bench + noise
    stock = bench * 1.5 + pd.Series(np.random.randn(n)) * 0.5
    out = factor_beta(stock, bench, period=60)
    valid = out.dropna()
    # Beta 应该接近 1.5
    assert valid.iloc[-1] == pytest.approx(1.5, abs=0.3)


def test_factor_beta_zero_variance():
    """零方差基准：Beta = NaN，不应崩"""
    bench = pd.Series([100.0] * 100)
    stock = pd.Series(np.cumsum(np.random.randn(100)))
    out = factor_beta(stock, bench, period=60)
    # 0/0 = NaN
    assert out.isna().all()


# ── 截面排名 ─────────────────────────────────────────

def test_cross_sectional_rank_ascending():
    """升序排名：值越大 rank 越大（1=最小，N=最大）"""
    df = pd.DataFrame({
        "trade_date": ["d1"] * 3 + ["d2"] * 3,
        "ticker": ["A", "B", "C", "A", "B", "C"],
        "pe_ttm": [10, 20, 30, 15, 25, 5],
    })
    out = cross_sectional_rank(df, "pe_ttm", ascending=True)
    # d1: A=1, B=2, C=3
    # d2: C=1, A=2, B=3
    d1 = out.iloc[:3].tolist()
    d2 = out.iloc[3:].tolist()
    assert d1 == [1.0, 2.0, 3.0]
    assert d2 == [2.0, 3.0, 1.0]


def test_cross_sectional_rank_descending():
    """降序排名：值越大 rank 越小（1=最大，N=最小）"""
    df = pd.DataFrame({
        "trade_date": ["d1"] * 3,
        "ticker": ["A", "B", "C"],
        "pe_ttm": [10, 20, 30],
    })
    out = cross_sectional_rank(df, "pe_ttm", ascending=False)
    # A=3, B=2, C=1（值越大 rank 越小）
    assert out.iloc[0] == 3.0  # A=10 → rank 3
    assert out.iloc[1] == 2.0  # B=20 → rank 2
    assert out.iloc[2] == 1.0  # C=30 → rank 1


# ── 因子方向一致性 ─────────────────────────────────

def test_value_factors_desc():
    """估值类（PE/PB/PS）应都是 desc（越小越好）"""
    for name in ["pe_ttm", "pb", "ps_ttm"]:
        assert FACTOR_REGISTRY[name]["direction"] == "desc", f"{name} 应为 desc"


def test_growth_factors_asc():
    """成长类（ROE/ROA/增速）应都是 asc（越大越好）"""
    for name in ["roe", "roa", "revenue_yoy", "profit_yoy"]:
        assert FACTOR_REGISTRY[name]["direction"] == "asc", f"{name} 应为 asc"


def test_volatility_factors_desc():
    """波动类应都是 desc（低波动偏好）"""
    for name in ["atr_pct", "hist_vol_20d"]:
        assert FACTOR_REGISTRY[name]["direction"] == "desc", f"{name} 应为 desc"
