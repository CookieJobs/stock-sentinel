"""股票告警核心 — 站内通知 + Webhook 推送"""
import os
import json
import sqlite3
import threading
import logging
from datetime import datetime
from typing import Optional

import requests

from models import StockResponse

logger = logging.getLogger(__name__)


class AlertDeduplicator:
    """告警去重 — 同一 ticker 每天最多一条"""

    def should_alert(self, ticker: str) -> bool:
        """今天是否已告警过"""
        from database import get_db
        conn = get_db()
        try:
            from datetime import date
            today = date.today().isoformat()
            row = conn.execute(
                "SELECT 1 FROM alert_history WHERE ticker = ? AND sent_date = ?",
                (ticker, today),
            ).fetchone()
            return row is None
        finally:
            conn.close()

    def mark_alerted(self, stock: StockResponse):
        """标记已告警"""
        from database import get_db
        conn = get_db()
        try:
            from datetime import date
            today = date.today().isoformat()
            conn.execute(
                """INSERT OR IGNORE INTO alert_history
                   (ticker, sent_date, event_type, drawdown_pct, threshold)
                   VALUES (?, ?, 'breach', ?, ?)""",
                (stock.ticker, today, stock.drawdown, stock.threshold),
            )
            conn.commit()
        finally:
            conn.close()


class AlertUnreadStore:
    """未读告警存储"""

    def add(self, stock: StockResponse, event_type: str = "breach"):
        from database import get_db
        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO alert_unread
                   (ticker, name, market, drawdown_pct, threshold, current_price, week52_high, week52_high_date, event_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    stock.ticker,
                    stock.name,
                    stock.market,
                    stock.drawdown,
                    stock.threshold,
                    stock.current_price,
                    stock.week52_high,
                    stock.week52_high_date,
                    event_type,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_all(self) -> list:
        from database import get_db
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM alert_unread ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def count(self) -> int:
        from database import get_db
        conn = get_db()
        try:
            row = conn.execute("SELECT COUNT(*) FROM alert_unread").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def clear_all(self):
        from database import get_db
        conn = get_db()
        try:
            conn.execute("DELETE FROM alert_unread")
            conn.commit()
        finally:
            conn.close()

    def get_history(self, limit: int = 50) -> list:
        from database import get_db
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM alert_history ORDER BY sent_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_history(self, alert_id: int) -> bool:
        from database import get_db
        conn = get_db()
        try:
            cursor = conn.execute("DELETE FROM alert_history WHERE id = ?", (alert_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def clear_history(self):
        from database import get_db
        conn = get_db()
        try:
            conn.execute("DELETE FROM alert_history")
            conn.commit()
        finally:
            conn.close()


class AlertStateStore:
    """告警状态机：只在首次越线时触发，明显恢复后才重新布防。"""

    def __init__(self, recovery_buffer_pct: Optional[float] = None):
        configured = recovery_buffer_pct
        if configured is None:
            configured = float(os.environ.get("ALERT_RECOVERY_BUFFER_PCT", "2"))
        self.recovery_buffer_pct = max(0.1, float(configured))
        self.max_quote_age_minutes = max(
            1, int(os.environ.get("ALERT_MAX_QUOTE_AGE_MINUTES", "120"))
        )

    def transition(self, stock: StockResponse) -> Optional[str]:
        """应用当前回撤并返回 breach/recovered；没有状态变化时返回 None。"""
        if not stock.alert_enabled:
            return None
        if stock.drawdown is None or stock.threshold is None or stock.threshold <= 0:
            return None
        if not self._has_usable_market_data(stock):
            return None

        db = self._get_row(stock.ticker)
        was_breached = bool(db["is_breached"]) if db else False
        is_breached = stock.drawdown <= -stock.threshold

        if is_breached:
            self._save(stock.ticker, True, stock.drawdown)
            return None if was_breached else "breach"

        # 对已越线标的采用回撤滞后，避免价格在阈值附近来回时反复提醒。
        recovery_buffer = min(self.recovery_buffer_pct, stock.threshold / 2)
        recovery_line = -(stock.threshold - recovery_buffer)
        if was_breached and stock.drawdown > recovery_line:
            self._save(stock.ticker, False, stock.drawdown)
            return "recovered"

        if db:
            self._save(stock.ticker, was_breached, stock.drawdown)
        return None

    def _has_usable_market_data(self, stock: StockResponse) -> bool:
        """阻止明显异常或过期行情成为用户的风险提醒依据。"""
        if stock.drawdown > 0 or stock.drawdown <= -95:
            logger.warning("Suppressing anomalous drawdown alert for %s: %s", stock.ticker, stock.drawdown)
            return False
        if not stock.last_updated:
            return True
        try:
            updated = datetime.fromisoformat(stock.last_updated.replace("Z", "+00:00"))
            now = datetime.now(updated.tzinfo) if updated.tzinfo else datetime.now()
            age_minutes = (now - updated).total_seconds() / 60
        except (TypeError, ValueError):
            logger.warning("Suppressing alert with invalid update time for %s", stock.ticker)
            return False
        if age_minutes > self.max_quote_age_minutes:
            logger.info("Suppressing stale alert for %s (%.0f minutes old)", stock.ticker, age_minutes)
            return False
        return True

    def clear(self, ticker: str):
        from database import get_db
        conn = get_db()
        try:
            conn.execute("DELETE FROM alert_state WHERE ticker = ?", (ticker.upper(),))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _get_row(ticker: str):
        from database import get_db
        conn = get_db()
        try:
            return conn.execute(
                "SELECT * FROM alert_state WHERE ticker = ?", (ticker.upper(),)
            ).fetchone()
        finally:
            conn.close()

    @staticmethod
    def _save(ticker: str, is_breached: bool, drawdown: float):
        from database import get_db
        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO alert_state
                   (ticker, is_breached, last_drawdown, breached_at, recovered_at, updated_at)
                   VALUES (?, ?, ?,
                           CASE WHEN ? THEN CURRENT_TIMESTAMP END,
                           CASE WHEN ? THEN CURRENT_TIMESTAMP END,
                           CURRENT_TIMESTAMP)
                   ON CONFLICT(ticker) DO UPDATE SET
                     is_breached = excluded.is_breached,
                     last_drawdown = excluded.last_drawdown,
                     breached_at = CASE WHEN excluded.is_breached = 1
                                        THEN CURRENT_TIMESTAMP ELSE alert_state.breached_at END,
                     recovered_at = CASE WHEN excluded.is_breached = 0
                                         THEN CURRENT_TIMESTAMP ELSE alert_state.recovered_at END,
                     updated_at = CURRENT_TIMESTAMP""",
                (ticker.upper(), int(is_breached), drawdown, int(is_breached), int(not is_breached)),
            )
            conn.commit()
        finally:
            conn.close()


def format_alert_message(stock: StockResponse) -> str:
    currency = {"CN": "¥", "HK": "HK$", "US": "$"}.get(stock.market, "$")
    return (
        f"[StockSentinel 告警] {stock.ticker} 回撤超限\n"
        f"股票：{stock.name} ({stock.ticker})\n"
        f"市场：{stock.market}\n"
        f"当前 1 年回撤：{stock.drawdown:.2f}%\n"
        f"阈值：{abs(stock.threshold):.2f}%\n"
        f"现价：{currency}{stock.current_price:.2f}\n"
        f"1 年高点：{currency}{stock.week52_high:.2f} ({stock.week52_high_date})"
    )


def check_stock_alert(stock: StockResponse, dedup: AlertDeduplicator) -> bool:
    """检查单只股票是否应触发告警"""
    if not stock.alert_enabled:
        return False
    if stock.drawdown is None or stock.threshold is None:
        return False
    if stock.threshold <= 0:
        return False
    if stock.drawdown > -stock.threshold:
        return False
    return dedup.should_alert(stock.ticker)


class StockAlerter:
    """股票告警器 — 站内通知"""

    def __init__(self):
        self.dedup = AlertDeduplicator()
        self.unread = AlertUnreadStore()
        self.state = AlertStateStore()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._interval = int(os.environ.get("ALERT_CHECK_INTERVAL", 300))
        self._enabled = os.environ.get("ALERT_ENABLED", "true").lower() == "true"
        self._webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")

    def start(self):
        if not self._enabled:
            logger.info("Alert disabled")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Alerter started, interval=%ds", self._interval)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._check_all()
            except Exception:
                logger.exception("Alert check failed")
            self._stop.wait(self._interval)

    def _check_all(self):
        """检查所有股票并发送站内告警"""
        from monitor import StockMonitor
        monitor = StockMonitor()
        stocks = monitor.get_all_stocks()
        alerted = []
        for stock in stocks:
            transition = self.state.transition(stock)
            if transition == "recovered":
                logger.info("Alert rearmed after recovery: %s", stock.ticker)
                continue
            if transition != "breach" or not self.dedup.should_alert(stock.ticker):
                continue
            self.unread.add(stock)
            self.dedup.mark_alerted(stock)
            alerted.append(stock.ticker)
            logger.info("Alert triggered: %s (%s)", stock.ticker, stock.name)
            self._send_webhook(stock)
        if alerted:
            logger.info("Alerted tickers: %s", alerted)

    def _send_webhook(self, stock: StockResponse):
        """向配置的 webhook URL 发送 Slack 兼容告警消息"""
        if not self._webhook_url:
            return
        currency = {"CN": "¥", "HK": "HK$", "US": "$"}.get(stock.market, "$")
        try:
            payload = {
                "text": (
                    f"🚨 *StockSentinel 告警* — {stock.ticker} 回撤超限\n"
                    f"股票：{stock.name} ({stock.ticker})\n"
                    f"市场：{stock.market}\n"
                    f"当前回撤：{stock.drawdown:.2f}%\n"
                    f"阈值：{abs(stock.threshold):.2f}%\n"
                    f"现价：{currency}{stock.current_price:.2f}\n"
                    f"52W高：{currency}{stock.week52_high:.2f} ({stock.week52_high_date})"
                )
            }
            resp = requests.post(self._webhook_url, json=payload, timeout=10)
            if resp.status_code >= 400:
                logger.warning("Webhook failed for %s: HTTP %s", stock.ticker, resp.status_code)
        except Exception:
            logger.exception("Webhook send error for %s", stock.ticker)

    def trigger_check(self):
        """手动触发一次检查"""
        self._check_all()
