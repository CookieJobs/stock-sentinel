"""模拟交易服务测试 — mock 行情价格，验证买卖/现金/盈亏/净值

运行: pytest backend/tests/quant_engine/test_paper_service.py -v
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import database
import quant_engine.db as qdb
import quant_engine.paper_service as ps

_ORIG_DB_PATH = database.DB_PATH
_ORIG_QDB_PATH = qdb.DB_PATH


def _use_tmp_db():
    tmp = Path(tempfile.mkdtemp(prefix="sentinel_paper_")) / "test.db"
    database.DB_PATH = tmp
    qdb.DB_PATH = tmp
    qdb.init_quant_db()
    return tmp


def _restore_db():
    database.DB_PATH = _ORIG_DB_PATH
    qdb.DB_PATH = _ORIG_QDB_PATH


PRICES = {"600519": (1307.88, "CN"), "000001": (11.27, "CN")}


def _fake_info(ticker):
    if ticker in PRICES:
        price, market = PRICES[ticker]
        return {"source": "tencent", "current_price": price, "market": market}
    return None   # 无真实行情


def test_buy_sell_flow():
    """买入扣现金建仓、卖出回现金计盈亏、现金不足/持仓不足拒绝"""
    tmp = _use_tmp_db()
    try:
        ps.DF.get_stock_info = staticmethod(_fake_info)
        pid = ps.create_portfolio("测试组合", 200000)["id"]

        t = ps.trade(pid, "600519", "buy", 100)
        assert t["amount"] == 130788.0

        d = ps.get_detail(pid)
        assert len(d["positions"]) == 1
        assert d["positions"][0]["qty"] == 100
        assert d["portfolio"]["cash"] == 200000 - 130788.0
        assert d["total_value"] == 200000.0  # 现金 + 持仓按成本

        # 现金不足
        try:
            ps.trade(pid, "600519", "buy", 1000)
            assert False, "应拒绝现金不足"
        except ValueError:
            pass

        # 卖出 40 股：价格 1307.88 = 成本 → 盈亏 0
        t2 = ps.trade(pid, "600519", "sell", 40)
        assert t2["realized_pnl"] == 0.0
        d2 = ps.get_detail(pid)
        assert d2["positions"][0]["qty"] == 60

        # 持仓不足
        try:
            ps.trade(pid, "600519", "sell", 1000)
            assert False, "应拒绝持仓不足"
        except ValueError:
            pass

        # 价格变化后 mark：600519 现价 1500 → 浮盈
        PRICES["600519"] = (1500.0, "CN")
        m = ps.mark_to_market(pid)
        expect = d2["portfolio"]["cash"] + 60 * 1500.0
        assert abs(m["equity"] - expect) < 1.0
        assert len(ps.get_detail(pid)["equity_curve"]) == 1
    finally:
        PRICES["600519"] = (1307.88, "CN")
        _restore_db()


def test_no_price_rejected():
    """无真实行情拒绝成交"""
    tmp = _use_tmp_db()
    try:
        ps.DF.get_stock_info = staticmethod(_fake_info)
        pid = ps.create_portfolio("测试", 10000)["id"]
        try:
            ps.trade(pid, "999999", "buy", 10)   # 不在 PRICES → None
            assert False, "应拒绝无行情成交"
        except ValueError:
            pass
    finally:
        _restore_db()


def test_close_and_delete():
    tmp = _use_tmp_db()
    try:
        ps.DF.get_stock_info = staticmethod(_fake_info)
        pid = ps.create_portfolio("测试", 10000)["id"]
        assert ps.close_portfolio(pid) is True
        try:
            ps.trade(pid, "600519", "buy", 1)
            assert False, "已关闭组合应拒绝交易"
        except ValueError:
            pass
        assert ps.delete_portfolio(pid) is True
    finally:
        _restore_db()


if __name__ == "__main__":
    tests = [test_buy_sell_flow, test_no_price_rejected, test_close_and_delete]
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
