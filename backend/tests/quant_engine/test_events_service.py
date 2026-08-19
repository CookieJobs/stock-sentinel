"""事件日历服务测试 — mock Tushare 响应，不消耗真实配额

运行: pytest backend/tests/quant_engine/test_events_service.py -v
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import database
import quant_engine.db as qdb
import quant_engine.events_service as es

_ORIG_DB_PATH = database.DB_PATH
_ORIG_QDB_PATH = qdb.DB_PATH
_ORIG_TOKEN = os.environ.get("TUSHARE_TOKEN")


def _use_tmp_db():
    tmp = Path(tempfile.mkdtemp(prefix="sentinel_evt_")) / "test.db"
    database.DB_PATH = tmp
    qdb.DB_PATH = tmp
    qdb.init_quant_db()
    return tmp


def _restore_db():
    database.DB_PATH = _ORIG_DB_PATH
    qdb.DB_PATH = _ORIG_QDB_PATH


DIVIDEND_FIELDS = ["ts_code", "end_date", "ann_date", "div_proc", "stk_div",
                   "record_date", "ex_date", "pay_date"]
DIVIDEND_ITEMS = [
    ["600519.SH", "20251231", "20260801", "实施", "27.9", "20260828", "20260831", "20260901"],
    ["000001.SZ", "20251231", "20260810", "股东大会通过", None, None, None, None],  # 无 ex_date → 客户端过滤丢弃
]
FLOAT_FIELDS = ["ts_code", "float_date", "float_share", "float_ratio", "holder_name", "share_type"]
FLOAT_ITEMS = [
    ["603583.SH", "20260910", "3489000.0", "0.9044", "核心技术/业务人员(共263人)", "股权激励限售流通"],
    ["000002.SZ", "20260701", "1000.0", "0.1", "某股东", "首发原股东限售"],  # 超范围 → 过滤
]


def _fake_ts_call(api_name, params, fields=""):
    if api_name == "dividend":
        return DIVIDEND_FIELDS, DIVIDEND_ITEMS
    if api_name == "share_float":
        return FLOAT_FIELDS, FLOAT_ITEMS
    return None


def test_refresh_and_list():
    """refresh 落库 + list 查询：类型、日期、范围过滤正确"""
    tmp = _use_tmp_db()
    os.environ["TUSHARE_TOKEN"] = "fake-token"
    try:
        es._ts_call = _fake_ts_call
        result = es.refresh_events("2026-08-20", "2026-09-20")
        assert result["inserted"] == 2, result          # 1 分红 + 1 解禁（各过滤掉 1 条）
        assert result["dividend"] == 1
        assert result["share_float"] == 1

        events = es.list_events("2026-08-20", "2026-09-20")
        assert len(events) == 2
        by_type = {e["event_type"]: e for e in events}
        div = by_type["dividend"]
        assert div["ticker"] == "600519"
        assert div["event_date"] == "2026-08-31"
        assert "27.9" in div["title"]
        assert '"record_date": "2026-08-28"' in div["detail"]
        flo = by_type["share_float"]
        assert flo["ticker"] == "603583"
        assert flo["event_date"] == "2026-09-10"
        assert "占流通 0.9044%" in flo["title"]

        # 类型过滤
        only_div = es.list_events("2026-08-20", "2026-09-20", event_type="dividend")
        assert len(only_div) == 1 and only_div[0]["event_type"] == "dividend"
    finally:
        if _ORIG_TOKEN is None:
            os.environ.pop("TUSHARE_TOKEN", None)
        else:
            os.environ["TUSHARE_TOKEN"] = _ORIG_TOKEN
        _restore_db()


def test_norm_date():
    assert es._norm_date("20260831") == "2026-08-31"
    assert es._norm_date("2026-08-31") == "2026-08-31"
    assert es._norm_date(None) is None


if __name__ == "__main__":
    tests = [test_refresh_and_list, test_norm_date]
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
