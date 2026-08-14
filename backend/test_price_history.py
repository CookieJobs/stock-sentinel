"""历史行情落库（price_history）测试 — 临时 DB，不污染真实数据

运行: python backend/test_price_history.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import database

_TMP_DIR = tempfile.mkdtemp(prefix="sentinel_test_")
database.DB_PATH = Path(_TMP_DIR) / "test.db"   # 所有 get_db() 走临时库


def _init_db():
    """每个用例独立临时库：删库重建，避免用例间数据串扰"""
    if database.DB_PATH.exists():
        database.DB_PATH.unlink()
    database.init_db()


def _fake_data(ticker="AAPL", source="eastmoney", price=200.0, drawdown=-25.0, change=-2.5):
    return {
        "ticker": ticker,
        "market": "CN",
        "name": "测试股",
        "source": source,
        "current_price": price,
        "change_pct": change,
        "drawdown": drawdown,
        "week52_high": 266.0,
    }


def _count(ticker=None):
    db = database.get_db()
    try:
        if ticker:
            return db.execute(
                "SELECT COUNT(*) FROM price_history WHERE ticker = ?", (ticker,)
            ).fetchone()[0]
        return db.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    finally:
        db.close()


def test_bucket_alignment():
    """北京时间分钟对齐 15：42 → 30，07 → 00"""
    from datetime import datetime, timezone, timedelta
    from monitor import StockMonitor
    bj = timezone(timedelta(hours=8))
    assert StockMonitor._price_bucket(datetime(2026, 1, 1, 10, 42, 0, tzinfo=bj)) == "2026-01-01 10:30"
    assert StockMonitor._price_bucket(datetime(2026, 1, 1, 10, 7, 0, tzinfo=bj)) == "2026-01-01 10:00"
    assert StockMonitor._price_bucket(datetime(2026, 1, 1, 10, 0, 0, tzinfo=bj)) == "2026-01-01 10:00"


def test_record_point_fields():
    """落库一行，字段齐全"""
    from monitor import StockMonitor
    _init_db()
    m = StockMonitor()
    m._record_price_point(_fake_data())
    db = database.get_db()
    try:
        row = db.execute("SELECT * FROM price_history WHERE ticker='AAPL'").fetchone()
    finally:
        db.close()
    assert row is not None
    assert row["bucket"] and row["captured_at"]
    assert row["current_price"] == 200.0
    assert row["drawdown"] == -25.0
    assert row["market"] == "CN"


def test_record_idempotent_same_bucket():
    """同 ticker 同桶二次写入不新增行（INSERT OR REPLACE 幂等）"""
    from monitor import StockMonitor
    _init_db()
    m = StockMonitor()
    m._record_price_point(_fake_data(price=200.0))
    m._record_price_point(_fake_data(price=205.0))   # 同 15 分钟窗口 → 覆盖
    assert _count("AAPL") == 1
    db = database.get_db()
    try:
        row = db.execute("SELECT current_price FROM price_history WHERE ticker='AAPL'").fetchone()
    finally:
        db.close()
    assert row["current_price"] == 205.0


def test_demo_not_recorded():
    """demo 回退数据不落库（与 monitor 守卫语义一致）"""
    from monitor import StockMonitor
    _init_db()
    m = StockMonitor()
    m._record_price_point(_fake_data(source="demo"))
    m._record_price_point(None)
    assert _count() == 0


def test_retention_cleanup():
    """写入时惰性清理超过保留期的旧行"""
    from datetime import datetime, timezone, timedelta
    from monitor import StockMonitor
    _init_db()
    old = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=120)).isoformat()
    db = database.get_db()
    try:
        db.execute(
            """INSERT INTO price_history
               (ticker, market, name, bucket, current_price, change_pct, drawdown, week52_high, captured_at)
               VALUES ('AAPL', 'CN', '测试', '2026-01-01 10:00', 100.0, 0.0, 0.0, 100.0, ?)""",
            (old,),
        )
        db.commit()
    finally:
        db.close()
    assert _count("AAPL") == 1
    m = StockMonitor()
    m._record_price_point(_fake_data(price=200.0))   # 触发清理
    assert _count("AAPL") == 1                        # 旧行被清，只留新行


def test_api_flow():
    """API 冒烟：有数据返回序列，无数据返回空 points（200）"""
    from fastapi.testclient import TestClient
    from main import app
    from monitor import StockMonitor
    _init_db()
    m = StockMonitor()
    m._record_price_point(_fake_data(ticker="AAPL", price=200.0, drawdown=-25.0))
    c = TestClient(app)

    r = c.get("/api/history/AAPL")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ticker"] == "AAPL"
    assert data["market"] == "CN"
    assert len(data["points"]) == 1
    assert data["points"][0]["drawdown"] == -25.0
    assert data["points"][0]["captured_at"]

    r2 = c.get("/api/history/999999")
    assert r2.status_code == 200
    assert r2.json()["points"] == []

    r3 = c.get("/api/history/AAPL?days=999")
    assert r3.status_code == 200
    assert r3.json()["days"] == 90   # 上限截断


if __name__ == "__main__":
    tests = [
        test_bucket_alignment,
        test_record_point_fields,
        test_record_idempotent_same_bucket,
        test_demo_not_recorded,
        test_retention_cleanup,
        test_api_flow,
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
