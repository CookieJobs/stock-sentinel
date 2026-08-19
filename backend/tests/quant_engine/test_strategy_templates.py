"""策略模板测试 — 结构校验 + API 冒烟

运行: pytest backend/tests/quant_engine/test_strategy_templates.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from quant_engine.strategy_templates import TEMPLATES, get_templates
from quant_engine.backtest import SIGNAL_REGISTRY


def test_templates_structure():
    """模板字段完整、id 唯一、策略合法、参数可解析"""
    ids = [t["id"] for t in TEMPLATES]
    assert len(ids) == len(set(ids)), "template id 必须唯一"
    assert len(TEMPLATES) >= 3
    for t in TEMPLATES:
        assert t["strategy"] in SIGNAL_REGISTRY, f"未知策略: {t['strategy']}"
        assert t["name"] and t["description"]
        assert isinstance(t["params"], dict)
        assert isinstance(t["tickers"], list) and t["tickers"]
        assert t["rebalance_freq"] in ("daily", "weekly", "monthly", "quarterly", "none")


def test_get_templates_returns_copy():
    """get_templates 返回副本，外部修改不影响源数据"""
    t = get_templates()
    t[0]["name"] = "HACKED"
    assert TEMPLATES[0]["name"] != "HACKED"


def test_templates_api():
    """API 冒烟：GET /api/quant/backtest/templates"""
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.get("/api/quant/backtest/templates")
    assert r.status_code == 200
    ts = r.json()["templates"]
    assert len(ts) == len(TEMPLATES)
    assert {t["id"] for t in ts} == {t["id"] for t in TEMPLATES}


if __name__ == "__main__":
    tests = [test_templates_structure, test_get_templates_returns_copy, test_templates_api]
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
