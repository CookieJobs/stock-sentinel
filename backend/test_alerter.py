"""回撤风险关注提醒测试，使用临时 SQLite 数据库。"""
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import database

_TMP_DIR = tempfile.mkdtemp(prefix="sentinel_alert_test_")
database.DB_PATH = Path(_TMP_DIR) / "test.db"


def _reset_db():
    if database.DB_PATH.exists():
        database.DB_PATH.unlink()
    database.init_db()


def _insert_stock(ticker="AAPL", drawdown=-16.0, threshold=15.0, alert_enabled=True,
                  last_updated=None):
    if last_updated is None:
        last_updated = datetime.now(timezone.utc).isoformat()
    db = database.get_db()
    try:
        db.execute(
            """INSERT INTO stocks
               (ticker, name, market, threshold, alert_enabled, current_price, week52_high,
                drawdown, last_updated)
               VALUES (?, ?, 'US', ?, ?, 100.0, 120.0, ?, ?)""",
            (ticker, ticker, threshold, int(alert_enabled), drawdown, last_updated),
        )
        db.commit()
    finally:
        db.close()


class AlwaysEligible:
    """隔离持久化去重，只验证阈值规则本身。"""

    def should_alert(self, ticker: str) -> bool:
        return True


def test_positive_threshold_crossing_is_alertable():
    """正数 15% 是用户输入的风险线，回撤 -16% 必须可触发。"""
    from alerter import check_stock_alert
    from models import StockResponse

    stock = StockResponse(
        ticker="AAPL", threshold=15.0, drawdown=-16.0, alert_enabled=True
    )

    assert check_stock_alert(stock, AlwaysEligible()) is True


def test_disabled_threshold_never_alerts():
    """关闭提醒后，即使回撤越线也不能创建风险通知。"""
    from alerter import check_stock_alert
    from models import StockResponse

    stock = StockResponse(
        ticker="AAPL", threshold=15.0, drawdown=-16.0, alert_enabled=False
    )

    assert check_stock_alert(stock, AlwaysEligible()) is False


def test_alert_state_rearms_only_after_meaningful_recovery():
    """持续超限仅触发一次，回撤收窄超过 2pp 后才重新布防。"""
    from alerter import AlertStateStore
    from models import StockResponse

    _reset_db()
    state = AlertStateStore()
    breached = StockResponse(
        ticker="AAPL", threshold=15.0, drawdown=-16.0, alert_enabled=True
    )

    assert state.transition(breached) == "breach"
    assert state.transition(breached.model_copy(update={"drawdown": -17.0})) is None
    assert state.transition(breached.model_copy(update={"drawdown": -12.9})) == "recovered"
    assert state.transition(breached) == "breach"


def test_legacy_negative_threshold_migrates_without_losing_enablement():
    """旧库的负数启用语义迁移为正数风险线和显式开关。"""
    if database.DB_PATH.exists():
        database.DB_PATH.unlink()
    conn = sqlite3.connect(database.DB_PATH)
    try:
        conn.execute(
            """CREATE TABLE stocks (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               ticker TEXT NOT NULL UNIQUE,
               name TEXT NOT NULL,
               market TEXT NOT NULL DEFAULT 'US',
               threshold REAL NOT NULL DEFAULT 0.0)"""
        )
        conn.executemany(
            "INSERT INTO stocks (ticker, name, market, threshold) VALUES (?, ?, 'US', ?)",
            [("LEGACY_ON", "Legacy on", -15.0), ("LEGACY_OFF", "Legacy off", 0.0)],
        )
        conn.commit()
    finally:
        conn.close()

    database.init_db()
    db = database.get_db()
    try:
        rows = db.execute(
            "SELECT ticker, threshold, alert_enabled FROM stocks ORDER BY ticker"
        ).fetchall()
    finally:
        db.close()
    assert [tuple(row) for row in rows] == [
        ("LEGACY_OFF", 0.0, 0),
        ("LEGACY_ON", 15.0, 1),
    ]
    _reset_db()


def test_alerter_creates_one_unread_record_for_a_persistent_breach():
    """持久在线的越线状态只产生一次未读和一次历史快照。"""
    from alerter import StockAlerter

    _reset_db()
    _insert_stock()
    alerter = StockAlerter()

    alerter._check_all()
    alerter._check_all()

    db = database.get_db()
    try:
        assert db.execute("SELECT COUNT(*) FROM alert_unread").fetchone()[0] == 1
        row = db.execute(
            "SELECT event_type, drawdown_pct, threshold FROM alert_history WHERE ticker = 'AAPL'"
        ).fetchone()
    finally:
        db.close()
    assert tuple(row) == ("breach", -16.0, 15.0)


def test_alerter_suppresses_stale_and_anomalous_market_data():
    """超过新鲜度上限或近乎归零的异常回撤不能作为提醒依据。"""
    from alerter import StockAlerter

    _reset_db()
    _insert_stock(
        ticker="STALE",
        last_updated=(datetime.now(timezone.utc) - timedelta(minutes=121)).isoformat(),
    )
    _insert_stock(ticker="BROKEN", drawdown=-99.0)

    StockAlerter()._check_all()

    db = database.get_db()
    try:
        assert db.execute("SELECT COUNT(*) FROM alert_unread").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM alert_history").fetchone()[0] == 0
    finally:
        db.close()


def test_deleting_a_stock_removes_its_alert_state():
    """删除后重新添加同代码，不能继承已经越线的旧状态。"""
    from monitor import StockMonitor

    _reset_db()
    _insert_stock()
    db = database.get_db()
    try:
        db.execute(
            "INSERT INTO alert_state (ticker, is_breached, last_drawdown) VALUES ('AAPL', 1, -16.0)"
        )
        db.commit()
    finally:
        db.close()

    assert StockMonitor().delete_stock("AAPL") is True

    db = database.get_db()
    try:
        assert db.execute("SELECT COUNT(*) FROM alert_state WHERE ticker = 'AAPL'").fetchone()[0] == 0
    finally:
        db.close()


if __name__ == "__main__":
    tests = [
        test_positive_threshold_crossing_is_alertable,
        test_disabled_threshold_never_alerts,
        test_alert_state_rearms_only_after_meaningful_recovery,
        test_legacy_negative_threshold_migrates_without_losing_enablement,
        test_alerter_creates_one_unread_record_for_a_persistent_breach,
        test_alerter_suppresses_stale_and_anomalous_market_data,
        test_deleting_a_stock_removes_its_alert_state,
    ]
    passed = 0
    try:
        for test in tests:
            test()
            print(f"PASS  {test.__name__}")
            passed += 1
    finally:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
    print(f"\n{passed}/{len(tests)} tests passed")
    sys.exit(0 if passed == len(tests) else 1)
