"""股票搜索服务测试 — 市场分类规则 / 多源合并去重 / 本地降级 / API 集成

覆盖：
- `classify_market`：CN A/B 股、指数、债券、HK 正股（新旧 SecurityType）、HK 债券、US 普通股/ADR/ETF/Notes、
  英股/韩股 → 正确归类或排除
- `search_stocks`：mock 东财 suggest → 结果去重、market 过滤、limit 生效
- 本地降级：东财不可达时自选表/量化名称表兜底（conftest 已把 DB 重定向到临时库）
- API：GET /api/quant/search 形状 + 422 校验
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from fastapi.testclient import TestClient

import database
from main import app
from quant_engine import search_service
from quant_engine.db import get_quant_db, init_quant_db
from quant_engine.api import search as search_api

# 确保量化表存在（conftest 已把 DB 重定向到临时库，不会碰真实库）
init_quant_db()
# 确保 v0.2.0 stocks 表存在（本地降级测试用）
database.init_db()

# ── classify_market ────────────────────────────────

def _item(**kw) -> dict:
    base = {"Code": "X", "Name": "X", "MktNum": "1", "SecurityType": "1", "TypeUS": "1"}
    base.update(kw)
    return base


@pytest.mark.parametrize("item,expected", [
    # CN A/B 股
    (_item(MktNum="1", SecurityType="1"), "CN"),   # 沪A
    (_item(MktNum="0", SecurityType="2"), "CN"),   # 深A
    (_item(MktNum="0", SecurityType="4"), "CN"),   # 深B
    # CN 非股票：指数 / 债券
    (_item(MktNum="1", SecurityType="5"), None),   # 指数
    (_item(MktNum="1", SecurityType="16"), None),  # 债券
    # HK 正股（新旧 SecurityType 均收，需 TypeUS=3）
    (_item(MktNum="116", SecurityType="19", TypeUS="3"), "HK"),
    (_item(MktNum="116", SecurityType="6", TypeUS="3"), "HK"),
    # HK 债券（SecurityType=6 但 TypeUS=2）
    (_item(MktNum="116", SecurityType="6", TypeUS="2"), None),
    # US：普通股 / ADR / ETF 收，Notes 排除
    (_item(MktNum="105", SecurityType="7", TypeUS="1"), "US"),
    (_item(MktNum="106", SecurityType="20", TypeUS="3"), "US"),
    (_item(MktNum="107", SecurityType="7", TypeUS="5"), "US"),
    (_item(MktNum="105", SecurityType="7", TypeUS="6"), None),  # Notes
    # 其他市场排除
    (_item(MktNum="155", SecurityType="24", TypeUS="1"), None),  # 英股
    (_item(MktNum="177", SecurityType="51", TypeUS="2"), None),  # 韩股
])
def test_classify_market(item, expected):
    assert search_service.classify_market(item) == expected


# ── search_stocks（mock 东财） ──────────────────────

@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """默认屏蔽真实网络，测试自己控制 suggest 返回"""
    monkeypatch.setattr(search_service, "_em_suggest", lambda q, count: None)


def _mock_items(*items):
    def fake(q, count):
        return [dict(it) for it in items[:count]]
    return fake


def test_search_merges_and_dedups(monkeypatch):
    """东财多条同股（沪A+深B 同码不冲突、同 market+ticker 去重）"""
    items = [
        _item(Code="600519", Name="贵州茅台", MktNum="1", SecurityType="1"),
        _item(Code="600519", Name="贵州茅台", MktNum="1", SecurityType="1"),  # 重复
        _item(Code="00700", Name="腾讯控股", MktNum="116", SecurityType="19", TypeUS="3"),
        _item(Code="AAPL", Name="苹果", MktNum="105", SecurityType="7", TypeUS="1"),
        _item(Code="751074", Name="招商银行债", MktNum="1", SecurityType="16"),  # 债券应过滤
    ]
    monkeypatch.setattr(search_service, "_em_suggest", _mock_items(*items))
    results = search_service.search_stocks("茅台", limit=10)
    keys = [(r["market"], r["ticker"]) for r in results]
    assert len(keys) == len(set(keys)), "结果必须按 (market, ticker) 去重"
    assert ("CN", "600519") in keys
    assert ("HK", "00700") in keys
    assert ("US", "AAPL") in keys
    assert ("CN", "751074") not in keys


def test_search_market_filter(monkeypatch):
    """market=HK 时只保留港股结果"""
    items = [
        _item(Code="00700", Name="腾讯控股", MktNum="116", SecurityType="19", TypeUS="3"),
        _item(Code="000700", Name="模塑科技", MktNum="0", SecurityType="2"),
    ]
    monkeypatch.setattr(search_service, "_em_suggest", _mock_items(*items))
    results = search_service.search_stocks("00700", market="HK")
    assert [(r["ticker"], r["market"]) for r in results] == [("00700", "HK")]


def test_search_limit(monkeypatch):
    items = [_item(Code=f"60000{i}", Name=f"股票{i}", MktNum="1", SecurityType="1") for i in range(3)]
    monkeypatch.setattr(search_service, "_em_suggest", _mock_items(*items))
    assert len(search_service.search_stocks("股", limit=2)) == 2


def test_search_local_fallback(monkeypatch):
    """东财不可达（_em_suggest 返回 None）时本地自选表兜底"""
    ticker, name = "ZTEST9", "测试股票九号"
    db = database.get_db()
    db.execute("DELETE FROM stocks WHERE ticker = ?", (ticker,))
    db.execute(
        "INSERT INTO stocks (ticker, name, market) VALUES (?, ?, ?)",
        (ticker, name, "CN"),
    )
    db.commit()
    try:
        results = search_service.search_stocks("测试股票九号")
        assert any(r["ticker"] == ticker and r["name"] == name and r["source"] == "local" for r in results)
    finally:
        db.execute("DELETE FROM stocks WHERE ticker = ?", (ticker,))
        db.commit()


def test_search_prefers_eastmoney_over_local(monkeypatch):
    """东财与本地同股时以 (market, ticker) 去重且不覆盖东财名称"""
    ticker = "ZTEST8"
    db = database.get_db()
    db.execute("DELETE FROM stocks WHERE ticker = ?", (ticker,))
    db.execute("INSERT INTO stocks (ticker, name, market) VALUES (?, ?, ?)", (ticker, "本地旧名", "CN"))
    db.commit()
    try:
        monkeypatch.setattr(
            search_service, "_em_suggest",
            _mock_items(_item(Code=ticker, Name="东财新名", MktNum="1", SecurityType="1")),
        )
        results = search_service.search_stocks(ticker)
        match = next(r for r in results if r["ticker"] == ticker)
        assert match["name"] == "东财新名" and match["source"] == "eastmoney"
    finally:
        db.execute("DELETE FROM stocks WHERE ticker = ?", (ticker,))
        db.commit()


# ── API 集成 ───────────────────────────────────────

def test_api_search(monkeypatch):
    # api/search.py 在 import 时绑定 search_stocks，需 patch 模块级引用
    monkeypatch.setattr(
        search_api, "search_stocks",
        lambda q, limit=10, market=None: [
            {"ticker": "600519", "name": "贵州茅台", "market": "CN", "source": "eastmoney"},
        ],
    )
    resp = TestClient(app).get("/api/quant/search", params={"q": "茅台"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "茅台"
    assert body["results"][0]["ticker"] == "600519"
    assert body["results"][0]["name"] == "贵州茅台"


@pytest.mark.parametrize("params", [
    {},                                    # 缺 q
    {"q": ""},                             # q 为空
    {"q": "x", "market": "JP"},            # 非法市场
    {"q": "x", "limit": 0},                # limit 越界
])
def test_api_search_validation(params):
    resp = TestClient(app).get("/api/quant/search", params=params)
    assert resp.status_code == 422


def test_quant_db_name_tables_exist():
    """降级源依赖的表结构必须存在（防静默失效）"""
    qdb = get_quant_db()
    tables = {r[0] for r in qdb.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('ts_universe_cache','daily_metrics')"
    )}
    assert {"ts_universe_cache", "daily_metrics"} <= tables
