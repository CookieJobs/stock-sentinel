"""同花顺数据源测试 — mock HTTP，验证信封解析/批量分页/指标映射/因子源

运行: pytest backend/tests/quant_engine/test_ths_source.py -v
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import database
import quant_engine.db as qdb
from quant_engine.data_source.ths_source import (
    THSApiClient, THSValuationFactorSource,
    ticker_to_thscode, latest_report, INDICATOR_MAP,
)

_ORIG_DB_PATH = database.DB_PATH
_ORIG_QDB_PATH = qdb.DB_PATH
_ORIG_KEY = os.environ.get("THS_API_KEY")


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    """按 URL 返回预置响应的假 session"""
    def __init__(self, responses):
        self._responses = responses   # {substring: payload}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        for key, payload in self._responses.items():
            if key in url:
                return FakeResp(payload)
        return FakeResp({"code": 9999, "message": "unexpected"})


def _mk_client(responses):
    os.environ["THS_API_KEY"] = "fake-key"
    c = THSApiClient()
    c.session = FakeSession(responses)
    return c


def test_ticker_to_thscode():
    assert ticker_to_thscode("600519") == "600519.SH"
    assert ticker_to_thscode("000001") == "000001.SZ"
    assert ticker_to_thscode("300750") == "300750.SZ"
    assert ticker_to_thscode("830799") == "830799.BJ"
    assert ticker_to_thscode("600519", "SSE") == "600519.SH"
    assert ticker_to_thscode("600519", "SZSE") == "600519.SZ"


def test_latest_report():
    """按披露日历：1-4 月取上年年报，5-9 月中报，10-12 月三季报"""
    assert latest_report(2026, 1) == "2025-4"
    assert latest_report(2026, 4) == "2025-4"
    assert latest_report(2026, 5) == "2026-2"
    assert latest_report(2026, 8) == "2026-2"
    assert latest_report(2026, 10) == "2026-3"
    assert latest_report(2026, 12) == "2026-3"


def test_financial_indicators_latest_fallback():
    """当期报告未披露（5003）→ 自动回退到上一期"""
    from quant_engine.data_source.ths_source import financial_indicators_latest
    empty_payload = {"code": 0, "data": {"abilities": []}}
    good_payload = {"code": 0, "data": {"abilities": [
        {"ability": "profitability", "indicators": [
            {"index_id": "index_weighted_avg_roe", "value": "15.0"}]},
    ]}}

    class FlakySession:
        def __init__(self):
            self.calls = []
        def get(self, url, params=None, timeout=None):
            self.calls.append(params)
            report = (params or {}).get("report", "")
            payload = good_payload if report == "2026-2" else empty_payload
            return FakeResp(payload)

    os.environ["THS_API_KEY"] = "fake-key"
    c = THSApiClient()
    c.session = FlakySession()
    mapped = financial_indicators_latest(c, "600519.SH", 2026, 8)
    assert mapped["roe"] == 15.0
    assert c.session.calls[0]["report"] == "2026-2"   # 当期中报直接命中


def test_valuations_batching_and_envelope():
    """150 个代码 → 2 批请求；信封 data.item 解析"""
    item = {"thscode": "600519.SH", "pe_ttm": "19.5", "pb": "6.3", "ps_ttm": "8.1", "pcf_ttm": None}
    c = _mk_client({"/api/a-share/valuations/snapshot": {"code": 0, "data": {"item": [item]}}})
    items = c.valuations_snapshot([f"{i:06d}.SZ" for i in range(150)])
    assert len(items) == 2
    assert c.session.calls[0][1]["thscodes"].count(",") == 99   # 第一批 100 个
    assert c.session.calls[1][1]["thscodes"].count(",") == 49   # 第二批 50 个


def test_error_envelope_raises():
    """code=2001（无/无效 key）→ ValueError"""
    c = _mk_client({"/": {"code": 2001, "message": "invalid api key"}})
    try:
        c._get("/api/a-share/valuations/snapshot", {})
        assert False, "应抛 ValueError"
    except ValueError as e:
        assert "2001" in str(e)


def test_financial_indicators_mapped():
    """财务指标 → 因子列映射（浮点化、None 保留）"""
    payload = {"code": 0, "data": {"thscode": "300033.SZ", "report": "2025-1", "abilities": [
        {"ability": "growth", "indicators": [
            {"index_id": "operating_income_yoy_growth_ratio", "value": "-16.0031"},
            {"index_id": "net_profit_yoy_growth_ratio", "value": None},
        ]},
        {"ability": "profitability", "indicators": [
            {"index_id": "sale_gross_margin", "value": "89.12000000"},
            {"index_id": "index_weighted_avg_roe", "value": "12.5"},
            {"index_id": "sale_net_interest_ratio", "value": "-3.2"},
            {"index_id": "total_assets_net_ratio", "value": "1.1"},
        ]},
        {"ability": "solvency", "indicators": [
            {"index_id": "assets_debt_ratio", "value": "45.6"},
        ]},
    ]}}
    c = _mk_client({"/api/a-share/financials/indicators": payload})
    m = c.financial_indicators_mapped("300033.SZ", "2025-1")
    assert m["revenue_yoy"] == -16.0031
    assert m["profit_yoy"] is None
    assert m["gross_margin"] == 89.12
    assert m["roe"] == 12.5
    assert m["net_margin"] == -3.2
    assert m["roa"] == 1.1
    assert m["debt_ratio"] == 45.6
    assert set(m) == set(INDICATOR_MAP.values())


def test_valuation_source_universe(monkeypatch):
    """因子源：从 ts_universe_cache 取代码表 → 批量估值 → df"""
    tmp = Path(tempfile.mkdtemp(prefix="sentinel_ths_")) / "test.db"
    database.DB_PATH = tmp
    qdb.DB_PATH = tmp
    qdb.init_quant_db()
    try:
        db = qdb.get_quant_db()
        db.executemany(
            "INSERT OR REPLACE INTO ts_universe_cache (ticker, exchange) VALUES (?, ?)",
            [("600519", "SSE"), ("000001", "SZSE")],
        )
        db.commit()
        db.close()

        payload = {"code": 0, "data": {"item": [
            {"thscode": "600519.SH", "pe_ttm": "19.5", "pb_mrq": "6.3", "ps_ttm": "8.1"},
            {"thscode": "000001.SZ", "pe_ttm": "5.1", "pb_mrq": "0.47", "ps_ttm": "1.0"},
        ]}}
        src = THSValuationFactorSource()
        src.client = _mk_client({"/api/a-share/valuations/snapshot": payload})
        df = src.get_universe()
        assert len(df) == 2
        assert set(df["ticker"]) == {"600519", "000001"}
        assert df["pe_ttm"].tolist() == [19.5, 5.1]
        assert df["pb"].tolist() == [6.3, 0.47]
        assert df["market"].tolist() == ["CN"] * 2
    finally:
        database.DB_PATH = _ORIG_DB_PATH
        qdb.DB_PATH = _ORIG_QDB_PATH
        if _ORIG_KEY is None:
            os.environ.pop("THS_API_KEY", None)
        else:
            os.environ["THS_API_KEY"] = _ORIG_KEY


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
