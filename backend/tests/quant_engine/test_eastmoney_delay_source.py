"""东财延时因子源测试 — mock clist 响应，验证分页/字段映射/数值化/单位换算

运行: pytest backend/tests/quant_engine/test_eastmoney_delay_source.py -v
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from quant_engine.data_source.eastmoney_delay_source import (
    EastMoneyDelayFactorSource, _FIELD_MAP,
)


class FakeResp:
    def __init__(self, data):
        self._data = data
        self.status_code = 200

    def json(self):
        return self._data


def _page_rows():
    return [
        {"f12": "300839", "f14": "博汇股份", "f100": "炼化及贸易",
         "f2": 12.47, "f3": 20.02, "f8": 6.74,
         "f9": 19.21, "f115": 100.56, "f116": "-", "f23": 4.46,
         "f20": 3593030244, "f21": 3531272033, "f37": 5.97},
        {"f12": "000001", "f14": "平安银行", "f100": "银行",
         "f2": 11.27, "f3": 1.99, "f8": 0.73,
         "f9": 5.03, "f115": 5.03, "f116": 1.0, "f23": 0.47,
         "f20": 218704698114, "f21": 200000000000, "f37": 11.5},
    ]


def test_pagination_and_mapping(monkeypatch):
    """两页分页抓取 + 字段映射 + ticker 补零 + market 标记"""
    calls = {"n": 0}
    page1_rows = (_page_rows() * 50)[:100]       # 第 1 页满 100 行（API 单页上限）
    pages = {
        1: FakeResp({"data": {"total": 101, "diff": page1_rows}}),
        2: FakeResp({"data": {"total": 101, "diff": [
            {"f12": "600519", "f14": "贵州茅台", "f100": "白酒",
             "f2": 1307.88, "f3": 0.76, "f8": 0.3,
             "f9": 25.2, "f115": 25.2, "f23": 8.0,
             "f20": 1643000000000, "f21": 1643000000000, "f37": 30.1}]}}),
    }

    def fake_get(url, params=None, timeout=None, headers=None):
        calls["n"] += 1
        return pages[params["pn"]]

    monkeypatch.setattr("quant_engine.data_source.eastmoney_delay_source.requests.get", fake_get)
    src = EastMoneyDelayFactorSource()
    df = src.get_universe()
    assert calls["n"] == 2                      # 分页抓了两页
    assert len(df) == 101
    assert df["market"].tolist() == ["CN"] * 101
    # 字段映射 + 数值化（查去重后的唯一行）
    row = df[df["ticker"] == "000001"].iloc[0]
    assert row["name"] == "平安银行"
    assert row["industry"] == "银行"
    assert row["pe_ttm"] == 5.03
    assert row["pb"] == 0.47
    assert row["roe"] == 11.5
    # 市值单位换算：元 → 万元（对齐 Tushare daily_basic）
    assert abs(row["market_cap"] - 21870469.8114) < 1e-3
    # ps_ttm 缺失值 '-' → NaN
    assert pd.isna(df[df["ticker"] == "300839"]["ps_ttm"].iloc[0])
    # 第二页数据也在
    moutai = df[df["ticker"] == "600519"].iloc[0]
    assert moutai["name"] == "贵州茅台" and moutai["industry"] == "白酒"


def test_empty_response(monkeypatch):
    """空响应返回空 DataFrame"""
    monkeypatch.setattr(
        "quant_engine.data_source.eastmoney_delay_source.requests.get",
        lambda *a, **k: FakeResp({"data": {"total": 0, "diff": []}}),
    )
    df = EastMoneyDelayFactorSource().get_universe()
    assert df is not None and df.empty


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
