"""每日简报模块测试 — 临时 DB，不污染真实数据

运行: python backend/test_briefing.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

# 保证 backend 在 sys.path 中（与 test_data_fetcher.py 相同约定）
sys.path.insert(0, str(Path(__file__).parent))

import database

_TMP_DIR = tempfile.mkdtemp(prefix="sentinel_test_")
database.DB_PATH = Path(_TMP_DIR) / "test.db"   # 所有 get_db() 走临时库


def _reset_db():
    """每个用例独立临时库：删库重建，避免用例间数据串扰"""
    if database.DB_PATH.exists():
        database.DB_PATH.unlink()
    database.init_db()


def _init_db():
    _reset_db()


def _insert_stock(ticker="AAPL", name="Apple Inc", market="US", drawdown=-25.0,
                  current_price=200.0, week52_high=266.0, change_pct=-2.5, threshold=-15.0):
    db = database.get_db()
    try:
        db.execute(
            """INSERT INTO stocks (ticker, name, market, threshold, current_price, change_pct,
                                   week52_high, drawdown)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, name, market, threshold, current_price, change_pct, week52_high, drawdown),
        )
        db.commit()
    finally:
        db.close()


def test_collect_snapshot_idempotent():
    """快照写入且幂等：同一天两次 collect 不产生重复行"""
    from briefing import BriefingGenerator
    g = BriefingGenerator()
    _init_db()
    _insert_stock()
    _insert_stock(ticker="0700", name="Tencent", market="HK", drawdown=-30.0,
                  current_price=400.0, week52_high=500.0, change_pct=1.2, threshold=-20.0)

    n1 = g.collect_snapshot("2026-01-01")
    n2 = g.collect_snapshot("2026-01-01")
    assert n1 == 2 and n2 == 2, f"collect 返回数量异常: {n1}, {n2}"

    db = database.get_db()
    try:
        cnt = db.execute("SELECT COUNT(*) FROM stock_snapshots WHERE snapshot_date='2026-01-01'").fetchone()[0]
    finally:
        db.close()
    assert cnt == 2, f"快照应保持幂等（2 行），实际 {cnt} 行"


def test_generate_template_content():
    """模板生成包含免责声明、监控数量、超阈值清单"""
    from briefing import BriefingGenerator
    g = BriefingGenerator()
    _init_db()
    _insert_stock()  # drawdown -25 vs threshold -15 → 超阈值
    result = g.generate("2026-01-02")
    briefing = result["briefing"]
    assert result["mode"] == "template"
    content = briefing["content"]
    assert "不构成投资建议" in content
    assert "监控 1 只" in content
    assert "AAPL" in content
    assert "超过回撤阈值的股票：1 只" in content
    # stats 落库
    assert briefing["stats"] and '"date": "2026-01-02"' in briefing["stats"]


def test_llm_fallback_no_key():
    """无 Key 时 _call_llm 返回 None（不抛异常）"""
    from briefing import BriefingGenerator, LLM_API_KEY
    g = BriefingGenerator()
    # 模块级常量在 import 时读 env；这里显式覆盖，避免依赖外部环境
    import briefing as b
    old_key, old_url = b.LLM_API_KEY, b.LLM_BASE_URL
    try:
        b.LLM_API_KEY = ""
        assert g._call_llm("s", "u") is None
        b.LLM_API_KEY = "fake-key"
        b.LLM_BASE_URL = "http://127.0.0.1:1/v1"   # 必然连接失败
        assert g._call_llm("s", "u") is None
    finally:
        b.LLM_API_KEY, b.LLM_BASE_URL = old_key, old_url


def test_api_flow():
    """API 冒烟：generate → latest → 列表"""
    from fastapi.testclient import TestClient
    from main import app
    _init_db()
    _insert_stock()
    c = TestClient(app)

    r = c.post("/api/briefings/generate")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mode"] == "template"
    assert data["briefing"]["briefing_date"]

    r2 = c.get("/api/briefings/latest")
    assert r2.status_code == 200
    assert r2.json()["content"]

    r3 = c.get("/api/briefings/")
    assert r3.status_code == 200
    assert len(r3.json()) >= 1


def test_scheduler_check_runs_without_error():
    """调度器解析时间 + 触发条件逻辑不抛异常"""
    from briefing import BriefingScheduler, today_beijing
    s = BriefingScheduler()
    assert s._parse_time().seconds == 8 * 3600 + 30 * 60   # 默认 08:30
    # 生成一次当日简报后，应判定"今日已生成"
    s.generator.generate()
    from briefing import has_briefing_on
    assert has_briefing_on(today_beijing()) is True


def test_trends_in_stats():
    """简报 stats 含 trends：top 回撤股票的 price_history 序列（点数<2 过滤）"""
    import json
    from briefing import BriefingGenerator
    g = BriefingGenerator()
    _init_db()
    _insert_stock()  # AAPL drawdown -25
    _insert_stock(ticker="0700", name="Tencent", market="HK", drawdown=-30.0,
                  current_price=400.0, week52_high=500.0, change_pct=1.2, threshold=-20.0)

    # 只给 AAPL 插 3 个历史点；0700 无历史点 → 应被过滤
    db = database.get_db()
    try:
        for i, dd in enumerate([-20.0, -23.0, -25.0]):
            db.execute(
                """INSERT OR REPLACE INTO price_history
                   (ticker, market, name, bucket, current_price, drawdown, week52_high, captured_at)
                   VALUES ('AAPL','US','Apple Inc',?, 200.0, ?, 266.0, ?)""",
                (f"2026-01-0{i+1} 10:00", dd, f"2026-01-0{i+1}T10:00:00+08:00"),
            )
        db.commit()
    finally:
        db.close()

    result = g.generate("2026-01-10")
    stats = json.loads(result["briefing"]["stats"])
    assert "trends" in stats
    tickers = [t["ticker"] for t in stats["trends"]]
    assert "AAPL" in tickers and "0700" not in tickers
    aapl = [t for t in stats["trends"] if t["ticker"] == "AAPL"][0]
    assert aapl["points"] == [-20.0, -23.0, -25.0]
    assert aapl["market"] == "US"


if __name__ == "__main__":
    tests = [
        test_collect_snapshot_idempotent,
        test_generate_template_content,
        test_llm_fallback_no_key,
        test_api_flow,
        test_scheduler_check_runs_without_error,
        test_trends_in_stats,
    ]
    passed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} tests passed")
    shutil.rmtree(_TMP_DIR, ignore_errors=True)
    sys.exit(0 if passed == len(tests) else 1)
