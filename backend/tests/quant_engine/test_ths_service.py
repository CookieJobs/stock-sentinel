"""同花顺财务指标 enrichment 服务测试 — mock 指标接口，验证缓存与 df 附加

运行: pytest backend/tests/quant_engine/test_ths_service.py -v
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import database
import quant_engine.db as qdb
import quant_engine.ths_service as ts

_ORIG_DB_PATH = database.DB_PATH
_ORIG_QDB_PATH = qdb.DB_PATH
_ORIG_KEY = os.environ.get("THS_API_KEY")


def _use_tmp_db():
    tmp = Path(tempfile.mkdtemp(prefix="sentinel_ths_svc_")) / "test.db"
    database.DB_PATH = tmp
    qdb.DB_PATH = tmp
    qdb.init_quant_db()
    # v0.2.0 stocks 表也要建（monitored 来源）
    db = database.get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL UNIQUE,
        name TEXT, market TEXT DEFAULT 'US', threshold REAL DEFAULT 0.0)""")
    db.execute("INSERT OR IGNORE INTO stocks (ticker, name, market) VALUES ('600519', '贵州茅台', 'CN')")
    db.execute("INSERT OR IGNORE INTO stocks (ticker, name, market) VALUES ('000001', '平安银行', 'CN')")
    db.execute("INSERT OR IGNORE INTO stocks (ticker, name, market) VALUES ('AAPL', '苹果', 'US')")
    db.commit()
    db.close()
    return tmp


def _restore():
    database.DB_PATH = _ORIG_DB_PATH
    qdb.DB_PATH = _ORIG_QDB_PATH
    if _ORIG_KEY is None:
        os.environ.pop("THS_API_KEY", None)
    else:
        os.environ["THS_API_KEY"] = _ORIG_KEY


def _fake_indicators(client, thscode, year, month):
    ticker = thscode.split(".")[0]
    return {"roe": 10.0, "roa": 5.0, "gross_margin": 90.0, "net_margin": 50.0,
            "debt_ratio": 12.0, "revenue_yoy": 15.0, "profit_yoy": 20.0,
            "_ticker": ticker}


def test_refresh_and_cache():
    """刷新落缓存；报告期未变时二次刷新不重拉"""
    tmp = _use_tmp_db()
    os.environ["THS_API_KEY"] = "fake-key"
    try:
        ts.financial_indicators_latest = _fake_indicators
        calls = {"n": 0}
        orig = ts.THSApiClient
        class FakeClient(orig):
            def __init__(self):
                super().__init__()
        # 统计调用次数：monkeypatch financial_indicators_latest 计数
        def counting(client, thscode, year, month):
            calls["n"] += 1
            return _fake_indicators(client, thscode, year, month)
        ts.financial_indicators_latest = counting

        n = ts.refresh_indicators(["600519", "000001"])
        assert n == 2
        assert calls["n"] == 2

        cached = ts.get_cached_indicators(["600519"])
        assert cached["600519"]["roe"] == 10.0
        assert cached["600519"]["gross_margin"] == 90.0

        # 报告期未变 → 二次刷新不重拉
        n2 = ts.refresh_indicators(["600519", "000001"])
        assert n2 == 0
        assert calls["n"] == 2
    finally:
        _restore()


def test_no_key_skips():
    """无 THS_API_KEY 时刷新返回 0"""
    _use_tmp_db()
    try:
        if os.environ.get("THS_API_KEY"):
            del os.environ["THS_API_KEY"]
        assert ts.refresh_indicators(["600519"]) == 0
    finally:
        _restore()


def test_enrich_universe_df():
    """enrich：监控股票的 df 行获得指标列（含缓存路径，不重复拉取）"""
    import pandas as pd
    _use_tmp_db()
    os.environ["THS_API_KEY"] = "fake-key"
    try:
        # 预置缓存（600519），000001 走拉取
        ts._cache_indicators("600519", ts.latest_report(2026, 8),
                             {"roe": 10.57, "gross_margin": 89.76})
        calls = {"n": 0}
        def counting(client, thscode, year, month):
            calls["n"] += 1
            t = thscode.split(".")[0]
            return {"roe": 2.83, "gross_margin": None, "debt_ratio": 90.98} if t == "000001" else {}
        ts.financial_indicators_latest = counting

        df = pd.DataFrame({
            "ticker": ["600519", "000001", "300750"],
            "pe_ttm": [19.5, 5.1, 21.3],
            "market": ["CN"] * 3,
        })
        out = ts.enrich_universe_df(df)
        assert calls["n"] == 1                       # 只拉 000001（600519 走缓存）
        assert out[out["ticker"] == "600519"]["roe"].iloc[0] == 10.57
        assert out[out["ticker"] == "600519"]["gross_margin"].iloc[0] == 89.76
        assert out[out["ticker"] == "000001"]["roe"].iloc[0] == 2.83
        assert out[out["ticker"] == "000001"]["debt_ratio"].iloc[0] == 90.98
        # 非监控股票 300750 → NaN（不参与排名）
        import math
        assert math.isnan(out[out["ticker"] == "300750"]["roe"].iloc[0])
    finally:
        _restore()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
