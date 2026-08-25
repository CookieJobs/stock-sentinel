"""AI 策略选股测试（v1.1）

覆盖：
- 内置策略结构校验（id 唯一 / 因子合法 / 范围合法 / explains 覆盖）
- 副本隔离 / get_strategy 错误
- validate_strategy 各种非法输入
- apply_strategy：整列为空因子跳过 + skipped_factors + ST 排除 + 正常筛选
- generate_strategy：LLM 成功 / 坏 JSON / 未知因子 / 非法范围 / 无 Key / 空 prompt
- API 集成：3 个端点冒烟
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from fastapi.testclient import TestClient

from quant_engine import screener_strategies as ss
from quant_engine.db import get_quant_db, init_quant_db
from quant_engine.factors import FACTOR_EXPLAINERS, FACTOR_REGISTRY


# ── 内置策略结构 ──────────────────────────────────────────────

def test_strategy_count_and_unique_ids():
    strategies = ss.get_strategies()
    assert len(strategies) >= 6
    ids = [s["id"] for s in strategies]
    assert len(ids) == len(set(ids)), "策略 id 必须唯一"


def test_strategy_structure_and_registry_validity():
    for s in ss.get_strategies():
        for key in ("id", "name", "tagline", "audience", "risk_level",
                    "filters", "rank_by", "top_n", "why", "explains"):
            assert s.get(key) is not None, f"{s['id']} 缺 {key}"
        assert isinstance(s["top_n"], int) and 1 <= s["top_n"] <= 200
        assert s["rank_by"] in ss.SCREENABLE_FIELDS, f"{s['id']} rank_by 非法: {s['rank_by']}"
        assert isinstance(s["filters"], list) and s["filters"], f"{s['id']} 无筛选条件"
        seen = set()
        for f in s["filters"]:
            factor = f["factor"]
            assert factor in ss.SCREENABLE_FIELDS, f"{s['id']} 因子非法: {factor}"
            assert factor not in seen, f"{s['id']} 因子重复: {factor}"
            seen.add(factor)
            lo, hi = f.get("min"), f.get("max")
            if lo is not None and hi is not None:
                assert lo <= hi, f"{s['id']} {factor} min>max"
        for factor in seen:
            assert factor in s["explains"], f"{s['id']} explains 未覆盖 {factor}"


def test_get_strategies_returns_copies():
    s1 = ss.get_strategies()
    s1[0]["name"] = "被改了"
    s1[0]["filters"].append({"factor": "pb", "max": 9})
    s2 = ss.get_strategies()
    assert s2[0]["name"] != "被改了"
    assert len(s2[0]["filters"]) == len(ss.SCREENER_STRATEGIES[0]["filters"])


def test_get_strategy_unknown():
    with pytest.raises(ss.StrategyError):
        ss.get_strategy("not_exist")


def test_factor_explainers_cover_all_factors():
    for f in FACTOR_REGISTRY:
        assert f in FACTOR_EXPLAINERS, f"因子 {f} 缺白话说明"
        assert FACTOR_EXPLAINERS[f]["desc"] and FACTOR_EXPLAINERS[f]["unit"]


# ── validate_strategy ─────────────────────────────────────────

def _valid_strategy():
    return {
        "name": "测试策略",
        "filters": [{"factor": "pe_ttm", "min": 0, "max": 30}],
        "rank_by": "pe_ttm",
        "top_n": 20,
    }


def test_validate_ok():
    ss.validate_strategy(_valid_strategy())  # 不抛即通过


@pytest.mark.parametrize("mutate,err", [
    (lambda s: s.update(name=""), "名字"),
    (lambda s: s.update(filters=[]), "筛选条件"),
    (lambda s: s.update(filters=[{"factor": "fake_xx", "max": 5}]), "未知因子"),
    (lambda s: s.update(filters=[{"factor": "pe_ttm", "min": 5, "max": 1}]), "min"),
    (lambda s: s.update(filters=[{"factor": "pe_ttm", "min": 5},
                                 {"factor": "pe_ttm", "max": 9}]), "重复"),
    (lambda s: s.update(rank_by="fake_yy"), "排名因子"),
    (lambda s: s.update(top_n=0), "top_n"),
    (lambda s: s.update(top_n=999), "top_n"),
    (lambda s: s.update(filters=[{"factor": "pe_ttm", "min": float("nan")}]), "合法数字"),
])
def test_validate_rejects(mutate, err):
    s = _valid_strategy()
    mutate(s)
    with pytest.raises(ss.StrategyError, match=err):
        ss.validate_strategy(s)


def test_validate_not_dict():
    with pytest.raises(ss.StrategyError):
        ss.validate_strategy("not a dict")


# ── apply_strategy（临时库造数）───────────────────────────────

def _seed_daily_metrics(rows):
    db = get_quant_db()
    try:
        cur = db.cursor()
        cur.execute("DELETE FROM daily_metrics")
        cur.executemany(
            """INSERT INTO daily_metrics
               (ticker, trade_date, name, industry, pe_ttm, pb, roe, gross_margin, turnover_rate)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def api_client():
    init_quant_db()
    from main import app
    return TestClient(app)


def test_apply_strategy_skips_empty_column_and_screens(api_client):
    """整列为空的因子（turnover_rate）跳过；正常因子照常筛选"""
    _seed_daily_metrics([
        ("600001", "2026-08-25", "测试甲", "银行", 10.0, 1.0, 20.0, 40.0, None),
        ("600002", "2026-08-25", "测试乙", "银行", 50.0, 3.0, 8.0, 10.0, None),
        ("600003", "2026-08-25", "测试丙", "银行", 15.0, 2.5, None, 30.0, None),
    ])
    strat = {"name": "测试", "filters": [
        {"factor": "pe_ttm", "min": 0, "max": 30},
        {"factor": "turnover_rate", "max": 10},
    ], "rank_by": "pe_ttm", "top_n": 10}
    r = ss.apply_strategy(strat)
    assert r["skipped_factors"] == ["turnover_rate"]
    tickers = [x["ticker"] for x in r["results"]]
    assert tickers == ["600001", "600003"], f"结果: {tickers}"


def test_apply_strategy_builtin_excludes_st_and_null(api_client):
    """内置 value_quality：ST 排除 + 因子值缺失行排除"""
    _seed_daily_metrics([
        ("600001", "2026-08-25", "测试甲", "银行", 10.0, 1.0, 20.0, None, 1.0),
        ("600002", "2026-08-25", "测试乙", "银行", 50.0, 3.0, 8.0, None, 1.0),
        ("600003", "2026-08-25", "*ST坏公司", "银行", 5.0, 0.5, 25.0, None, 1.0),
    ])
    r = ss.apply_strategy(ss.get_strategy("value_quality"))
    assert "roe" not in r["skipped_factors"]
    tickers = [x["ticker"] for x in r["results"]]
    assert tickers == ["600001"], f"结果: {tickers}"


def test_apply_strategy_empty_db(api_client):
    """空库：如实返回「请先刷新因子库」，不崩"""
    _seed_daily_metrics([])
    r = ss.apply_strategy(ss.get_strategy("deep_value"))
    assert "error" in r
    assert r["results"] == []


# ── generate_strategy（monkeypatch LLM）───────────────────────

def _mock_llm(monkeypatch, content):
    monkeypatch.setattr(ss, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(ss, "_call_llm", lambda system, user: content)


def test_generate_strategy_ok(monkeypatch):
    _mock_llm(monkeypatch, """```json
{"name": "低估值高分红", "tagline": "适合吃股息", "filters": [
  {"factor": "pe_ttm", "max": 20}, {"factor": "roe", "min": 10}],
 "rank_by": "pe_ttm", "top_n": 30, "why": "便宜又赚钱"}
```""")
    s = ss.generate_strategy("我想找低估值的高分红股")
    assert s["llm_generated"] is True
    assert s["id"].startswith("ai_")
    assert s["name"] == "低估值高分红"
    assert {f["factor"] for f in s["filters"]} == {"pe_ttm", "roe"}
    assert "pe_ttm" in s["explains"] and "roe" in s["explains"]
    assert s["rank_by"] == "pe_ttm" and s["top_n"] == 30


def test_generate_strategy_missing_optional_fields(monkeypatch):
    """LLM 漏掉 rank_by/top_n 时补默认值"""
    _mock_llm(monkeypatch, '{"name": "测试", "filters": [{"factor": "pb", "max": 3}]}')
    s = ss.generate_strategy("测试")
    assert s["rank_by"] == "pe_ttm"
    assert s["top_n"] == 20


def test_generate_strategy_bad_json(monkeypatch):
    _mock_llm(monkeypatch, '{"name": "x", "filters": [}')
    with pytest.raises(ss.StrategyError, match="无法解析"):
        ss.generate_strategy("测试")


def test_generate_strategy_unknown_factor(monkeypatch):
    _mock_llm(monkeypatch, '{"name": "x", "filters": [{"factor": "magic_ratio", "max": 3}]}')
    with pytest.raises(ss.StrategyError, match="未知因子"):
        ss.generate_strategy("测试")


def test_generate_strategy_invalid_range(monkeypatch):
    _mock_llm(monkeypatch, '{"name": "x", "filters": [{"factor": "pe_ttm", "min": 50, "max": 10}]}')
    with pytest.raises(ss.StrategyError, match="min"):
        ss.generate_strategy("测试")


def test_generate_strategy_no_key(monkeypatch):
    monkeypatch.setattr(ss, "LLM_API_KEY", "")
    with pytest.raises(ss.StrategyError, match="LLM_API_KEY"):
        ss.generate_strategy("测试")


def test_generate_strategy_empty_prompt(monkeypatch):
    with pytest.raises(ss.StrategyError, match="描述"):
        ss.generate_strategy("   ")


# ── API 集成 ──────────────────────────────────────────────────

def test_api_list_strategies(api_client):
    r = api_client.get("/api/quant/screener/strategies")
    assert r.status_code == 200
    data = r.json()
    assert len(data["strategies"]) >= 6
    assert isinstance(data["llm_configured"], bool)


def test_api_screen_by_strategy_id(api_client):
    _seed_daily_metrics([
        ("600001", "2026-08-25", "测试甲", "银行", 10.0, 1.0, 20.0, None, None),
        ("600002", "2026-08-25", "测试乙", "银行", 50.0, 3.0, 8.0, None, None),
        ("600005", "2026-08-25", "测试亏损股", "银行", -5.0, 0.8, -10.0, None, None),
    ])
    r = api_client.post("/api/quant/screener/screen", json={"strategy_id": "deep_value"})
    assert r.status_code == 200
    data = r.json()
    assert "skipped_factors" in data
    assert [x["ticker"] for x in data["results"]] == ["600001"]
    # desc 因子防御：PE/PB 未给 min 时默认 min=0，亏损股（负 PE）被排除
    applied = {f["factor"]: f for f in data["applied_filters"]}
    assert applied["pe_ttm"]["min"] == 0
    assert applied["pb"]["min"] == 0


def test_api_screen_invalid_strategy(api_client):
    r = api_client.post("/api/quant/screener/screen", json={"strategy_id": "nope"})
    assert r.status_code == 400


def test_api_screen_missing_payload(api_client):
    r = api_client.post("/api/quant/screener/screen", json={})
    assert r.status_code == 400


def test_api_generate_without_key(api_client, monkeypatch):
    monkeypatch.setattr(ss, "LLM_API_KEY", "")  # 显式无 Key，避免本机 env 真调 LLM
    r = api_client.post("/api/quant/screener/strategies/generate", json={"prompt": "测试"})
    assert r.status_code == 400
    assert "LLM" in r.json()["detail"]


def test_factors_list_has_plain_language(api_client):
    r = api_client.get("/api/quant/factors/list")
    assert r.status_code == 200
    factors = r.json()["factors"]
    assert len(factors) == len(FACTOR_REGISTRY)
    for f in factors:
        assert f["description_zh"], f"{f['name']} 缺白话说明"
        assert f["unit"], f"{f['name']} 缺单位"
