"""kline_service 数据清洗硬化测试

背景：K 线 NaN/±inf 序列化为 JSON null（或 allow_nan=False 直接 500），
前端 lightweight-charts 断言 'must be a number, got=object/undefined' 会崩图表
（/chart 白屏根因同族问题）。本测试覆盖：
- _to_float / _is_finite 对非有限值的处理
- get_kline_with_indicators 丢弃 OHLC 非有限行、指标值过滤 inf
- ths_source._resample_kline 四列 dropna
"""
import math

import pandas as pd
import pytest

from quant_engine import kline_service
from quant_engine.data_source.ths_source import _resample_kline


# ── _to_float ──────────────────────────────────────────────

def test_to_float_rejects_non_finite():
    assert kline_service._to_float(float("inf")) is None
    assert kline_service._to_float(float("-inf")) is None
    assert kline_service._to_float(float("nan")) is None
    assert kline_service._to_float(None) is None
    assert kline_service._to_float("abc") is None


def test_to_float_accepts_numbers_and_numeric_strings():
    assert kline_service._to_float(12.34567) == 12.3457
    assert kline_service._to_float("12.34") == 12.34
    assert kline_service._to_float(0) == 0.0
    assert kline_service._to_float(True) == 1.0


# ── _is_finite ─────────────────────────────────────────────

def test_is_finite():
    assert kline_service._is_finite(1.5) is True
    assert kline_service._is_finite("1.5") is True
    assert kline_service._is_finite(0) is True
    assert kline_service._is_finite(float("inf")) is False
    assert kline_service._is_finite(float("-inf")) is False
    assert kline_service._is_finite(float("nan")) is False
    assert kline_service._is_finite(None) is False
    assert kline_service._is_finite("abc") is False
    assert kline_service._is_finite(pd.NA) is False


# ── get_kline_with_indicators 清洗 ─────────────────────────

def _mk_df(**overrides):
    data = {
        "trade_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "open": [1.0, 2.0, 3.0],
        "high": [2.0, 3.0, 4.0],
        "low": [0.5, 1.5, 2.5],
        "close": [1.5, 2.5, 3.5],
        "volume": [100.0, 200.0, 300.0],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def test_with_indicators_drops_nan_ohlc_rows(monkeypatch):
    df = _mk_df(open=[1.0, float("nan"), 3.0])
    monkeypatch.setattr(kline_service, "get_or_fetch", lambda *a, **k: df)
    monkeypatch.setattr(kline_service, "get_kline_meta", lambda *a, **k: {"row_count": 3})
    out = kline_service.get_kline_with_indicators("TEST", "US", "1d")
    assert len(out["kline"]) == 2
    for r in out["kline"]:
        assert None not in (r["open"], r["high"], r["low"], r["close"])


def test_with_indicators_drops_inf_ohlc_rows(monkeypatch):
    df = _mk_df(close=[1.5, 2.5, float("inf")])
    monkeypatch.setattr(kline_service, "get_or_fetch", lambda *a, **k: df)
    monkeypatch.setattr(kline_service, "get_kline_meta", lambda *a, **k: {"row_count": 3})
    out = kline_service.get_kline_with_indicators("TEST", "US", "1d")
    assert len(out["kline"]) == 2
    assert out["kline"][-1]["close"] == 2.5


def test_with_indicators_excludes_inf_indicator_values(monkeypatch):
    # volume 不在价格四列中，inf 能穿过 df 级 dropna —— 专门测指标值过滤
    df = _mk_df(volume=[100.0, float("inf"), 300.0])
    fake_spec = {"fn": lambda volume: volume * 2, "inputs": ["volume"], "params": {}}
    monkeypatch.setitem(kline_service.INDICATORS, "FAKE_TEST", fake_spec)
    monkeypatch.setattr(kline_service, "get_or_fetch", lambda *a, **k: df)
    monkeypatch.setattr(kline_service, "get_kline_meta", lambda *a, **k: {"row_count": 3})
    out = kline_service.get_kline_with_indicators(
        "TEST", "US", "1d", indicator_specs=[{"name": "FAKE_TEST", "params": {}}],
    )
    values = out["indicators"]["FAKE_TEST"]["values"]
    assert len(values) == 2
    assert all(v["value"] is not None for v in values)
    assert [v["value"] for v in values] == [200.0, 600.0]


# ── ths_source._resample_kline ─────────────────────────────

def test_resample_kline_drops_all_nan_ohlc_groups():
    df = pd.DataFrame({
        "trade_date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-08", "2024-01-09"]),
        "open": [1.0, 2.0, float("nan"), float("nan")],
        "high": [3.0, 4.0, 5.0, 6.0],
        "low": [0.5, 1.0, 2.0, 3.0],
        "close": [2.5, 3.5, 4.5, 5.5],
        "volume": [100.0, 200.0, 300.0, 400.0],
        "amount": [1000.0, 2000.0, 3000.0, 4000.0],
    })
    out = _resample_kline(df, "W")
    assert len(out) == 1
    assert out.iloc[0]["open"] == 1.0
