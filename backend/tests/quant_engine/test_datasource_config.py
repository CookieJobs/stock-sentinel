"""数据源配置测试 — settings 读写/校验/三域链重排

运行: pytest backend/tests/quant_engine/test_datasource_config.py -v
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import database
import quant_engine.db as qdb
import datasource_config as dc

_ORIG_DB_PATH = database.DB_PATH
_ORIG_QDB_PATH = qdb.DB_PATH


def _use_tmp_db():
    tmp = Path(tempfile.mkdtemp(prefix="sentinel_ds_")) / "test.db"
    database.DB_PATH = tmp
    qdb.DB_PATH = tmp
    qdb.init_quant_db()
    database.init_db()   # settings 表（datasource_config 的存储）在 v0.2.0 schema
    return tmp


def _restore():
    database.DB_PATH = _ORIG_DB_PATH
    qdb.DB_PATH = _ORIG_QDB_PATH


class TushareS:
    name = "tushare"


class ThsS:
    name = "ths"


class EmDelayS:
    name = "eastmoney_delay"


class AkShareS:
    name = "akshare"


def test_config_read_write_validation():
    """默认 auto → 钉住 → 改回 auto；非法值拒绝"""
    _use_tmp_db()
    try:
        assert dc.get_override("realtime") is None
        assert dc.get_config()["realtime"]["mode"] == "auto"

        dc.set_override("realtime", "tencent")
        assert dc.get_override("realtime") == "tencent"
        assert dc.get_config()["realtime"]["mode"] == "fixed"

        dc.set_override("realtime", "auto")
        assert dc.get_override("realtime") is None

        try:
            dc.set_override("realtime", "baostock")   # realtime 域没有 baostock
            assert False, "应拒绝非法源"
        except ValueError:
            pass
        try:
            dc.set_override("unknown_domain", "x")
            assert False, "应拒绝未知域"
        except ValueError:
            pass
    finally:
        _restore()


def test_ordered_by_preference_factor():
    """factor 域钉住某源 → 排到链首，其余保持原序"""
    _use_tmp_db()
    try:
        chain = [TushareS, ThsS, EmDelayS]
        assert dc.ordered_by_preference(chain, "factor") == [TushareS, ThsS, EmDelayS]   # auto
        dc.set_override("factor", "ths")
        ordered = dc.ordered_by_preference(chain, "factor")
        assert ordered[0] is ThsS and ordered[1:] == [TushareS, EmDelayS]
        dc.set_override("factor", "auto")
        assert dc.ordered_by_preference(chain, "factor") == [TushareS, ThsS, EmDelayS]
    finally:
        _restore()


def test_ordered_kline_and_realtime():
    """kline/realtime 域重排同样生效；未收录的源名忽略"""
    _use_tmp_db()
    try:
        chain = [ThsS, AkShareS]
        dc.set_override("kline", "ths")
        assert dc.ordered_by_preference(chain, "kline") == [ThsS, AkShareS]
        dc.set_override("kline", "baostock")   # 合法值但不在链中 → 原样
        assert dc.ordered_by_preference(chain, "kline") == [ThsS, AkShareS]
        assert dc.get_config()["realtime"]["options"] == ["eastmoney", "tencent"]
    finally:
        _restore()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
