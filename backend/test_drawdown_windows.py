from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from data_fetcher import DataFetcher


def test_calculate_drawdown_windows_uses_each_window_high_low_and_dates():
    """各周期必须按其自身范围内的高低点计算，不能复用 52 周数据。"""
    bars = [
        {"trade_date": "2025-08-27", "high": 180.0, "low": 70.0},
        {"trade_date": "2025-08-28", "high": 160.0, "low": 75.0},
        {"trade_date": "2026-02-28", "high": 150.0, "low": 80.0},
        {"trade_date": "2026-05-28", "high": 140.0, "low": 95.0},
        {"trade_date": "2026-08-28", "high": 130.0, "low": 100.0},
    ]

    windows = DataFetcher.calculate_drawdown_windows(
        current_price=120.0,
        daily_bars=bars,
        as_of=datetime(2026, 8, 28, 14, 30, tzinfo=timezone.utc),
    )

    assert windows["3m"] == {
        "status": "ok",
        "period_start": "2026-05-28",
        "as_of": "2026-08-28",
        "high": 140.0,
        "high_date": "2026-05-28",
        "low": 95.0,
        "low_date": "2026-05-28",
        "drawdown": pytest.approx(-14.29),
        "distance_low_pct": pytest.approx(26.32),
    }
    assert windows["6m"] == {
        "status": "ok",
        "period_start": "2026-02-28",
        "as_of": "2026-08-28",
        "high": 150.0,
        "high_date": "2026-02-28",
        "low": 80.0,
        "low_date": "2026-02-28",
        "drawdown": pytest.approx(-20.0),
        "distance_low_pct": pytest.approx(50.0),
    }
    assert windows["1y"] == {
        "status": "ok",
        "period_start": "2025-08-28",
        "as_of": "2026-08-28",
        "high": 160.0,
        "high_date": "2025-08-28",
        "low": 75.0,
        "low_date": "2025-08-28",
        "drawdown": pytest.approx(-25.0),
        "distance_low_pct": pytest.approx(60.0),
    }


def test_calculate_drawdown_windows_marks_a_period_with_missing_history():
    bars = [
        {"trade_date": "2026-06-01", "high": 120.0, "low": 100.0},
        {"trade_date": "2026-08-28", "high": 115.0, "low": 105.0},
    ]

    windows = DataFetcher.calculate_drawdown_windows(
        current_price=110.0,
        daily_bars=bars,
        as_of=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )

    assert windows["3m"]["status"] == "insufficient_history"
    assert windows["3m"]["period_start"] == "2026-05-28"
    assert windows["6m"]["status"] == "insufficient_history"
    assert windows["1y"]["status"] == "insufficient_history"


def test_calculate_drawdown_windows_includes_current_price_as_todays_new_high():
    bars = [
        {"trade_date": "2025-08-28", "high": 150.0, "low": 80.0},
        {"trade_date": "2026-08-28", "high": 145.0, "low": 120.0},
    ]

    windows = DataFetcher.calculate_drawdown_windows(
        current_price=160.0,
        daily_bars=bars,
        as_of=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )

    assert windows["1y"]["high"] == 160.0
    assert windows["1y"]["high_date"] == "2026-08-28"
    assert windows["1y"]["drawdown"] == 0.0


def test_daily_history_cache_prevents_repeat_history_fetches_within_ttl():
    DataFetcher._daily_bar_cache.clear()
    calls = 0

    def loader():
        nonlocal calls
        calls += 1
        return [{"trade_date": "2026-08-28", "high": 100.0, "low": 90.0}]

    first = DataFetcher._cached_daily_bars("test:AAPL", loader)
    second = DataFetcher._cached_daily_bars("test:AAPL", loader)

    assert calls == 1
    assert second == first
