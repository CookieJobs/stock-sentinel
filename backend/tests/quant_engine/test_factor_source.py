"""Tushare 因子数据源缓存回退测试 — 模拟限流，不消耗真实 API 配额

验证：
1. 首次拉取成功 → 返回真实数据 + 写缓存（universe + daily）
2. stock_basic / daily_basic 限流 → 回退缓存，数据不丢

运行: pytest backend/tests/quant_engine/test_factor_source.py -v
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import database
import quant_engine.db as qdb

_ORIG_DB_PATH = database.DB_PATH
_ORIG_QDB_PATH = qdb.DB_PATH
_ORIG_TOKEN = os.environ.get("TUSHARE_TOKEN")


def _use_tmp_db():
    """每个用例独立临时库（自包含，不依赖 conftest 的重定向）"""
    tmp = Path(tempfile.mkdtemp(prefix="sentinel_ts_")) / "test.db"
    database.DB_PATH = tmp
    qdb.DB_PATH = tmp
    qdb.init_quant_db()
    return tmp


def _restore_db():
    database.DB_PATH = _ORIG_DB_PATH
    qdb.DB_PATH = _ORIG_QDB_PATH


class FakePro:
    """模拟 Tushare pro_api：可配置 stock_basic / daily_basic 抛限流"""

    def __init__(self, fail_basic=False, fail_daily=False):
        self.fail_basic = fail_basic
        self.fail_daily = fail_daily

    def stock_basic(self, **kw):
        if self.fail_basic:
            raise Exception("抱歉，您访问接口(stock_basic)频率超限(1次/小时)")
        return pd.DataFrame({
            "ts_code": ["000001.SZ", "600519.SH"],
            "name": ["平安银行", "贵州茅台"],
            "industry": ["银行", "白酒"],
            "market": ["主板", "主板"],
            "exchange": ["SZSE", "SSE"],
            "list_date": ["1991-04-03", "2001-08-27"],
        })

    def daily_basic(self, **kw):
        if self.fail_daily:
            raise Exception("抱歉，您访问接口(daily_basic)频率超限(1次/小时)")
        return pd.DataFrame({
            "ts_code": ["000001.SZ", "600519.SH"],
            "pe_ttm": [5.0, 25.0],
            "pb": [0.5, 8.0],
            "ps_ttm": [1.0, 12.0],
            "total_mv": [2000.0, 16000.0],
            "circ_mv": [1800.0, 15000.0],
            "turnover_rate": [0.5, 0.3],
            "pct_chg": [1.2, -0.5],
        })


def _make_source(pro):
    from quant_engine.data_source.factor_source import TushareFactorSource
    os.environ["TUSHARE_TOKEN"] = "fake-token"
    src = TushareFactorSource()
    src.pro = pro
    return src


def test_first_fetch_returns_real_data_and_caches():
    """首次成功：返回真实字段 + universe/daily 双缓存落库"""
    tmp = _use_tmp_db()
    try:
        src = _make_source(FakePro())
        df = src.get_universe()
        assert len(df) == 2
        assert set(df["ticker"]) == {"000001", "600519"}
        assert df["pe_ttm"].tolist() == [5.0, 25.0]
        assert df["industry"].tolist() == ["银行", "白酒"]
        db = qdb.get_quant_db()
        try:
            assert db.execute("SELECT COUNT(*) FROM ts_universe_cache").fetchone()[0] == 2
            assert db.execute("SELECT COUNT(*) FROM ts_daily_cache").fetchone()[0] == 2
        finally:
            db.close()
    finally:
        _restore_db()


def test_rate_limited_falls_back_to_cache():
    """第二次两个接口都限流 → 回退缓存，仍返回数据"""
    tmp = _use_tmp_db()
    try:
        src = _make_source(FakePro())
        df1 = src.get_universe()
        assert len(df1) == 2

        src.pro = FakePro(fail_basic=True, fail_daily=True)
        df2 = src.get_universe()
        assert len(df2) == 2
        assert df2["pe_ttm"].tolist() == [5.0, 25.0]   # 来自缓存
        assert df2["industry"].tolist() == ["银行", "白酒"]
    finally:
        _restore_db()


def test_no_cache_returns_empty():
    """从未成功过且接口限流 → 返回空（调用方继续降级）"""
    tmp = _use_tmp_db()
    try:
        src = _make_source(FakePro(fail_basic=True, fail_daily=True))
        df = src.get_universe()
        assert df is None or df.empty
    finally:
        _restore_db()


if __name__ == "__main__":
    tests = [test_first_fetch_returns_real_data_and_caches,
             test_rate_limited_falls_back_to_cache,
             test_no_cache_returns_empty]
    passed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except Exception:
            import traceback
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
