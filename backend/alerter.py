"""股票告警核心 — 站内通知"""
import os
import sqlite3
import threading
import logging
from datetime import datetime
from typing import Optional

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

    def mark_alerted(self, ticker: str):
        """标记已告警"""
        from database import get_db
        conn = get_db()
        try:
            from datetime import date
            today = date.today().isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO alert_history (ticker, sent_date) VALUES (?, ?)",
                (ticker, today),
            )
            conn.commit()
        finally:
            conn.close()


class AlertUnreadStore:
    """未读告警存储"""

    def add(self, stock: StockResponse):
        from database import get_db
        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO alert_unread
                   (ticker, name, market, drawdown_pct, threshold, current_price, week52_high, week52_high_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    stock.ticker,
                    stock.name,
                    stock.market,
                    stock.drawdown,
                    stock.threshold,
                    stock.current_price,
                    stock.week52_high,
                    stock.week52_high_date,
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


def format_alert_message(stock: StockResponse) -> str:
    currency = {"CN": "¥", "HK": "HK$", "US": "$"}.get(stock.market, "$")
    return (
        f"[StockSentinel 告警] {stock.ticker} 回撤超限\n"
        f"股票：{stock.name} ({stock.ticker})\n"
        f"市场：{stock.market}\n"
        f"当前回撤：{stock.drawdown:.2f}%\n"
        f"阈值：{abs(stock.threshold):.2f}%\n"
        f"现价：{currency}{stock.current_price:.2f}\n"
        f"52W高：{currency}{stock.week52_high:.2f} ({stock.week52_high_date})"
    )


def check_stock_alert(stock: StockResponse, dedup: AlertDeduplicator) -> bool:
    """检查单只股票是否应触发告警"""
    if stock.drawdown is None or stock.threshold is None:
        return False
    if stock.threshold >= 0:
        return False
    if abs(stock.drawdown) < abs(stock.threshold):
        return False
    return dedup.should_alert(stock.ticker)


class StockAlerter:
    """股票告警器 — 站内通知"""

    def __init__(self):
        self.dedup = AlertDeduplicator()
        self.unread = AlertUnreadStore()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._interval = int(os.environ.get("ALERT_CHECK_INTERVAL", 300))
        self._enabled = os.environ.get("ALERT_ENABLED", "true").lower() == "true"

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
            if check_stock_alert(stock, self.dedup):
                self.unread.add(stock)
                self.dedup.mark_alerted(stock.ticker)
                alerted.append(stock.ticker)
                logger.info("Alert triggered: %s (%s)", stock.ticker, stock.name)
        if alerted:
            logger.info("Alerted tickers: %s", alerted)

    def trigger_check(self):
        """手动触发一次检查"""
        self._check_all()