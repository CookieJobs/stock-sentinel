"""组合管理单测

测试 CRUD / 估值 / 再平衡 / 回测 payload
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest

from quant_engine.db import init_quant_db
from quant_engine.portfolio import (
    create_portfolio, list_portfolios, get_portfolio, delete_portfolio,
    add_holding, update_holding_weight, remove_holding,
    check_rebalance,
)
from quant_engine.portfolio_service import (
    valuation, rebalance_actions, to_backtest_payload,
)


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试前初始化 DB"""
    init_quant_db()
    yield


@pytest.fixture
def sample_portfolio():
    """3 只持仓的测试组合"""
    pid = create_portfolio(
        name="测试组合",
        description="单测用",
        benchmark="000300.SH",
        rebalance_freq="monthly",
    )
    add_holding(pid, "600519", "CN", 0.4)
    add_holding(pid, "000858", "CN", 0.3)
    add_holding(pid, "000001", "CN", 0.3)
    return pid


# ── CRUD ─────────────────────────────────────────────────

def test_create_portfolio():
    """创建组合：返回 id，能列出来"""
    pid = create_portfolio(name="Test1", benchmark="000300.SH")
    assert pid > 0
    portfolios = list_portfolios()
    assert any(p["id"] == pid for p in portfolios)


def test_create_portfolio_empty_name():
    """空 name 应该报错（由 API 层处理，这里测底层）"""
    pid = create_portfolio(name="")
    # 底层允许空 name，API 层会校验
    assert pid > 0


def test_get_portfolio_with_holdings(sample_portfolio):
    """获取组合 + 持仓"""
    p = get_portfolio(sample_portfolio)
    assert p is not None
    assert p["name"] == "测试组合"
    assert len(p["holdings"]) == 3
    tickers = {h["ticker"] for h in p["holdings"]}
    assert tickers == {"600519", "000858", "000001"}


def test_get_portfolio_not_found():
    """不存在的 id：返回 None"""
    assert get_portfolio(99999) is None


def test_delete_portfolio(sample_portfolio):
    """删除组合"""
    ok = delete_portfolio(sample_portfolio)
    assert ok is True
    assert get_portfolio(sample_portfolio) is None
    # 持仓也级联删除
    assert list_portfolios()  # 不应崩


def test_delete_nonexistent_portfolio():
    """删除不存在的组合：返回 False"""
    assert delete_portfolio(99999) is False


def test_add_holding(sample_portfolio):
    """添加持仓"""
    ok = add_holding(sample_portfolio, "000333", "CN", 0.2)
    assert ok is True
    p = get_portfolio(sample_portfolio)
    assert any(h["ticker"] == "000333" for h in p["holdings"])


def test_add_holding_duplicate(sample_portfolio):
    """重复添加同一 ticker：REPLACE 覆盖"""
    add_holding(sample_portfolio, "000333", "CN", 0.2)
    add_holding(sample_portfolio, "000333", "CN", 0.5)  # 应覆盖
    p = get_portfolio(sample_portfolio)
    holdings = [h for h in p["holdings"] if h["ticker"] == "000333"]
    assert len(holdings) == 1
    assert holdings[0]["weight"] == 0.5


def test_update_holding_weight(sample_portfolio):
    """更新持仓权重"""
    ok = update_holding_weight(sample_portfolio, "600519", 0.6)
    assert ok is True
    p = get_portfolio(sample_portfolio)
    h = next(h for h in p["holdings"] if h["ticker"] == "600519")
    assert h["weight"] == 0.6


def test_update_nonexistent_holding(sample_portfolio):
    """更新不存在的持仓：返回 False"""
    ok = update_holding_weight(sample_portfolio, "NONEXIST", 0.5)
    assert ok is False


def test_remove_holding(sample_portfolio):
    """删除持仓"""
    ok = remove_holding(sample_portfolio, "600519")
    assert ok is True
    p = get_portfolio(sample_portfolio)
    assert not any(h["ticker"] == "600519" for h in p["holdings"])


def test_remove_nonexistent_holding(sample_portfolio):
    """删除不存在的持仓：返回 False"""
    assert remove_holding(sample_portfolio, "NONEXIST") is False


# ── 估值 ─────────────────────────────────────────────────

def test_valuation_empty_portfolio():
    """空组合估值"""
    pid = create_portfolio(name="空组合")
    val = valuation(pid)
    assert val["total_value"] == 0
    assert val["holdings"] == []


def test_valuation_nonexistent():
    """不存在的组合：返回 error"""
    val = valuation(99999)
    assert "error" in val


def test_valuation_with_holdings(sample_portfolio):
    """有持仓的组合估值（可能部分 ticker 拉不到，drift 计算）"""
    val = valuation(sample_portfolio)
    assert "holdings" in val
    assert len(val["holdings"]) == 3
    assert "drift" in val
    # drift 长度应该等于 holdings 长度
    assert len(val["drift"]) == 3
    for d in val["drift"]:
        assert d["action"] in ("buy", "sell", "hold")


# ── 再平衡 ──────────────────────────────────────────────

def test_rebalance_no_drift(sample_portfolio):
    """无再平衡需求"""
    actions = rebalance_actions(sample_portfolio, total_capital=1_000_000, threshold=1.0)
    # 阈值 100% 时永不触发
    assert actions == []


def test_rebalance_threshold_filters(sample_portfolio):
    """阈值过滤"""
    actions = rebalance_actions(sample_portfolio, total_capital=1_000_000, threshold=0.5)
    # 阈值 50% 时部分 ticker drift 触发
    # 取决于数据源能不能拉到价
    for a in actions:
        assert a["delta_pct"] >= 0.5


def test_rebalance_nonexistent():
    """不存在组合：返回空"""
    assert rebalance_actions(99999) == []


# ── 回测 payload 转换 ─────────────────────────────────

def test_to_backtest_payload_basic(sample_portfolio):
    """基本转换"""
    payload = to_backtest_payload(sample_portfolio)
    assert payload["name"] == "测试组合 回测"
    assert payload["strategy"] == "fixed_weights"
    assert set(payload["tickers"]) == {"600519", "000858", "000001"}
    assert payload["params"]["weights"]["600519"] == 0.4
    assert payload["benchmark"] == "000300.SH"


def test_to_backtest_payload_custom_dates(sample_portfolio):
    """自定义日期"""
    payload = to_backtest_payload(
        sample_portfolio,
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_capital=500_000,
        rebalance_freq="quarterly",
    )
    assert payload["start_date"] == "2023-01-01"
    assert payload["end_date"] == "2023-12-31"


def test_to_backtest_payload_nonexistent():
    """不存在的组合：抛 ValueError"""
    with pytest.raises(ValueError):
        to_backtest_payload(99999)


def test_to_backtest_payload_empty_portfolio():
    """空组合：抛 ValueError"""
    pid = create_portfolio(name="空")
    with pytest.raises(ValueError, match="空"):
        to_backtest_payload(pid)


# ── check_rebalance (M0 旧版) ──────────────────────────

def test_check_rebalance_basic(sample_portfolio):
    """M0 版的 check_rebalance"""
    prices = {"600519": 100.0, "000858": 100.0, "000001": 100.0}
    result = check_rebalance(sample_portfolio, prices, threshold=0.05)
    assert "need_rebalance" in result
    assert "details" in result
    # 权重相等时无漂移
    assert result["need_rebalance"] is False


def test_check_rebalance_with_drift(sample_portfolio):
    """有漂移时检测"""
    # 当前价让 600519 涨 50%，其他不变
    prices = {"600519": 150.0, "000858": 100.0, "000001": 100.0}
    result = check_rebalance(sample_portfolio, prices, threshold=0.05)
    # 600519 当前权重 = 0.4 * 150 / (0.4*150+0.3*100+0.3*100) = 60/120 = 0.5
    # drift = 0.5 - 0.4 = 0.1 > 0.05 → 触发
    assert result["need_rebalance"] is True
    target_600519 = next(d for d in result["details"] if d["ticker"] == "600519")
    assert target_600519["action"] == "sell"  # 当前 > 目标，应卖
