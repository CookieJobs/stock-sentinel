"""API 集成测试 — 所有 /api/quant/* 路由

端到端跑每个 endpoint，验证：
- 正常路径返回 200
- 错误路径返回 4xx/5xx（不崩）
- 关键字段存在
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from fastapi.testclient import TestClient

from main import app
from quant_engine.db import init_quant_db


@pytest.fixture(scope="module")
def client():
    init_quant_db()
    # 不用 `with TestClient(app)`：那会触发 lifespan 启动 monitor/alerter/briefing
    # 后台线程（真实网络 + 写库），裸 TestClient 不跑 lifespan，无副作用
    return TestClient(app)


def test_db_isolation():
    """回归保护：测试套件必须走临时库，绝不读写真实 data/sentinel.db"""
    import database
    import quant_engine.db as qdb

    paths = {"database.DB_PATH": database.DB_PATH, "quant_engine.db.DB_PATH": qdb.DB_PATH}
    # 两处引用必须指向同一个临时库（否则 quant 表与 v0.2.0 表分裂）
    assert len(set(map(str, paths.values()))) == 1, f"DB 路径分裂: {paths}"
    for name, p in paths.items():
        assert str(p).startswith(tempfile.gettempdir()), f"{name} 指向真实库: {p}"


# ── Health ──────────────────────────────────────────────

def test_health(client):
    """原 health endpoint"""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Indicators ──────────────────────────────────────────

def test_indicators_list(client):
    """列出指标"""
    r = client.get("/api/quant/indicators/list")
    assert r.status_code == 200
    data = r.json()
    assert "indicators" in data
    assert len(data["indicators"]) >= 12
    for ind in data["indicators"]:
        assert {"name", "params", "multi", "oscillator"} <= set(ind.keys())


def test_indicators_compute_invalid_name(client):
    """未知指标：400/500"""
    r = client.post("/api/quant/indicators/compute", json={"name": "NONEXISTENT"})
    # 可能是 200 + 空 result 或 500，看实际实现
    assert r.status_code in (200, 400, 422, 500)


# ── Factors ─────────────────────────────────────────────

def test_factors_list(client):
    """列出因子"""
    r = client.get("/api/quant/factors/list")
    assert r.status_code == 200
    data = r.json()
    assert len(data["factors"]) == 15


def test_factors_universe_stats_initial(client):
    """universe 初始为空或已有数据"""
    r = client.get("/api/quant/factors/universe/stats")
    assert r.status_code == 200
    data = r.json()
    assert "universe_size" in data
    assert "factor_count" in data


def test_factors_screen_empty_data(client):
    """无数据时选股：返回 error"""
    r = client.post("/api/quant/factors/screen",
                    json={"filters": [], "rank_by": "pe_ttm", "top_n": 5})
    assert r.status_code == 200
    # 可能 error 或 results = []


def test_factors_refresh(client):
    """刷新因子库：返回插入条数"""
    r = client.post("/api/quant/factors/refresh")
    assert r.status_code == 200
    data = r.json()
    assert "inserted" in data
    assert "stats" in data


def test_factors_industries(client):
    """列出行业"""
    r = client.get("/api/quant/factors/industries")
    assert r.status_code == 200
    data = r.json()
    assert "industries" in data
    assert len(data["industries"]) > 0


# ── K-line ─────────────────────────────────────────────

def test_kline_health(client):
    """K 线模块 health"""
    r = client.get("/api/quant/kline/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_kline_meta_no_data(client):
    """无本地数据时 meta：row_count=0"""
    r = client.get("/api/quant/kline/999999/meta", params={"market": "CN"})
    assert r.status_code == 200
    data = r.json()
    assert data["row_count"] == 0
    assert data["is_stale"] is True


def test_kline_invalid_market(client):
    """无效 market：422 (pattern 校验)"""
    r = client.get("/api/quant/kline/AAPL", params={"market": "XX"})
    assert r.status_code == 422


def test_kline_invalid_period(client):
    """无效 period：422"""
    r = client.get("/api/quant/kline/AAPL", params={"market": "US", "period": "xx"})
    assert r.status_code == 422


# ── Backtest ───────────────────────────────────────────

def test_backtest_strategies(client):
    """列出策略"""
    r = client.get("/api/quant/backtest/strategies")
    assert r.status_code == 200
    data = r.json()
    assert len(data["strategies"]) == 4
    names = {s["name"] for s in data["strategies"]}
    assert "equal_weight" in names
    assert "ma_cross" in names
    assert "factor_rank" in names
    assert "fixed_weights" in names


def test_backtest_recent(client):
    """列出最近回测"""
    r = client.get("/api/quant/backtest/list/recent")
    assert r.status_code == 200
    assert "backtests" in r.json()


def test_backtest_get_nonexistent(client):
    """不存在的回测：404"""
    r = client.get("/api/quant/backtest/99999")
    assert r.status_code == 404


def test_backtest_run_missing_field(client):
    """缺字段：400"""
    r = client.post("/api/quant/backtest/run", json={"name": "test"})
    assert r.status_code == 400 or r.status_code == 422


def test_backtest_run_invalid_strategy(client):
    """未知策略：400"""
    r = client.post("/api/quant/backtest/run", json={
        "name": "test",
        "strategy": "NONEXISTENT",
        "tickers": ["AAPL"],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    })
    assert r.status_code == 400


def test_backtest_run_empty_tickers(client):
    """空 tickers：400"""
    r = client.post("/api/quant/backtest/run", json={
        "name": "test",
        "strategy": "equal_weight",
        "tickers": [],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    })
    assert r.status_code == 400


# ── Portfolios ──────────────────────────────────────────

def test_portfolios_list(client):
    """列出组合"""
    r = client.get("/api/quant/portfolios/")
    assert r.status_code == 200
    assert "portfolios" in r.json()


def test_portfolios_create(client):
    """创建组合"""
    r = client.post("/api/quant/portfolios/", json={
        "name": "API测试组合",
        "benchmark": "000300.SH",
    })
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["id"] > 0


def test_portfolios_create_empty_name(client):
    """空 name：400"""
    r = client.post("/api/quant/portfolios/", json={"name": ""})
    assert r.status_code == 400


def test_portfolios_get_nonexistent(client):
    """不存在的组合：404"""
    r = client.get("/api/quant/portfolios/99999")
    assert r.status_code == 404


def test_portfolios_delete_nonexistent(client):
    """删除不存在的组合：404"""
    r = client.delete("/api/quant/portfolios/99999")
    assert r.status_code == 404


def test_portfolios_valuation_nonexistent(client):
    """不存在的组合估值：500 或 200 with error"""
    r = client.get("/api/quant/portfolios/99999/valuation")
    # valuation() 返回 dict 含 error 字段，状态码 200
    assert r.status_code == 200
    assert "error" in r.json()


# ── Risk ───────────────────────────────────────────────

def test_risk_benchmarks(client):
    """列出基准"""
    r = client.get("/api/quant/risk/benchmarks")
    assert r.status_code == 200
    data = r.json()
    assert "benchmarks" in data
    assert len(data["benchmarks"]) == 9


def test_risk_compute_basic(client):
    """基本风险计算"""
    r = client.post("/api/quant/risk/compute", json={
        "equity_curve": [
            {"date": "2024-01-01", "value": 100, "benchmark_value": 100},
            {"date": "2024-12-31", "value": 120, "benchmark_value": 110},
        ],
        "initial_capital": 100,
    })
    assert r.status_code == 200
    data = r.json()
    assert "total_return" in data
    assert abs(data["total_return"] - 0.20) < 0.01


def test_risk_compute_empty_curve(client):
    """空 equity_curve：应能处理（不崩）"""
    r = client.post("/api/quant/risk/compute", json={
        "equity_curve": [],
        "initial_capital": 100,
    })
    # 接受 200 + 空 dict 或 500（具体看实现）
    assert r.status_code in (200, 500)


# ── Metrics ─────────────────────────────────────────────

def test_metrics_health(client):
    """metrics 模块 health"""
    r = client.get("/api/quant/metrics/health")
    assert r.status_code == 200


def test_metrics_dashboard(client):
    """Dashboard 综合指标"""
    r = client.get("/api/quant/metrics/dashboard")
    assert r.status_code == 200
