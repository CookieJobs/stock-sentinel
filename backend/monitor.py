"""股票监控核心逻辑 — CRUD + 数据刷新"""
import os
import uuid
import threading
import sqlite3
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from database import get_db
from models import StockResponse
from data_fetcher import DataFetcher


class StockMonitor:
    """股票监控器"""

    # 类级别：刷新任务进度追踪 {task_id: {total, done, current, status, error}}
    _refresh_tasks: Dict[str, dict] = {}
    _lock = threading.Lock()

    def __init__(self):
        self.api_key = os.environ.get("FINNHUB_API_KEY", "")
        self._auto_refresh_thread = None
        self._stop_auto_refresh = threading.Event()
        self._last_auto_refresh = None

    def start_auto_refresh(self):
        """启动后台自动刷新（仅美股 120s，A/港股 30s）"""
        self._stop_auto_refresh.clear()
        self._schedule_next_refresh()

    def stop_auto_refresh(self):
        self._stop_auto_refresh.set()
        if self._auto_refresh_thread:
            self._auto_refresh_thread.join(timeout=5)

    def _schedule_next_refresh(self):
        if self._stop_auto_refresh.is_set():
            return
        self._auto_refresh_thread = threading.Timer(30, self._auto_refresh_loop)
        self._auto_refresh_thread.daemon = True
        self._auto_refresh_thread.start()

    def _auto_refresh_loop(self):
        try:
            db = get_db()
            try:
                rows = db.execute("SELECT ticker, market FROM stocks").fetchall()
            finally:
                db.close()

            all_tickers = [r["ticker"] for r in rows]

            for ticker in all_tickers:
                if self._stop_auto_refresh.is_set():
                    return
                self._fetch_one_stock(ticker)
                time.sleep(0.2)

            self._last_auto_refresh = datetime.now(timezone(timedelta(hours=8))).isoformat()
        except Exception:
            pass
        finally:
            if not self._stop_auto_refresh.is_set():
                self._schedule_next_refresh()

    def get_last_auto_refresh(self) -> Optional[str]:
        return self._last_auto_refresh

    def _row_to_response(self, row: sqlite3.Row) -> StockResponse:
        """将数据库行转换为 StockResponse"""
        if row is None:
            return None
        return StockResponse(
            id=row["id"],
            ticker=row["ticker"],
            name=row["name"] or "",
            market=row["market"] or "US",
            threshold=row["threshold"] or 0.0,
            current_price=row["current_price"],
            change_pct=row["change_pct"],
            ah_change_pct=row["ah_change_pct"],
            ah_change_label=row["ah_change_label"],
            sector=row["sector"],
            week52_high=row["week52_high"],
            week52_low=row["week52_low"],
            week52_high_date=row["week52_high_date"],
            week52_low_date=row["week52_low_date"],
            drawdown=row["drawdown"],
            distance_low_pct=row["distance_low_pct"],
            pe_ratio=row["pe_ratio"],
            market_status=row["market_status"] or "未知",
            last_updated=row["last_updated"],
            created_at=row["created_at"],
        )

    def get_all_stocks(self) -> List[StockResponse]:
        """获取所有监控股票"""
        db = get_db()
        try:
            rows = db.execute("SELECT * FROM stocks ORDER BY id").fetchall()
            return [self._row_to_response(r) for r in rows]
        finally:
            db.close()

    def get_stock_by_ticker(self, ticker: str) -> Optional[StockResponse]:
        """根据 ticker 获取单只股票"""
        db = get_db()
        try:
            row = db.execute("SELECT * FROM stocks WHERE ticker = ?", (ticker.upper(),)).fetchone()
            return self._row_to_response(row) if row else None
        finally:
            db.close()

    def add_stock(self, ticker: str, threshold: float = 0.0) -> Optional[StockResponse]:
        """添加股票到监控列表"""
        ticker = ticker.strip().upper()
        db = get_db()
        try:
            existing = db.execute("SELECT id FROM stocks WHERE ticker = ?", (ticker,)).fetchone()
            if existing:
                return None

            data = DataFetcher.get_stock_info(ticker, self.api_key)
            name = ticker
            market = DataFetcher.detect_market(ticker)
            current_price = None
            change_pct = None
            ah_change_pct = None
            ah_change_label = None
            sector = None
            week52_high = None
            week52_low = None
            week52_high_date = None
            week52_low_date = None
            drawdown = None
            distance_low_pct = None
            pe_ratio = None
            market_status = "未知"
            last_updated = None

            if data:
                name = data.get("name", ticker)
                market = data.get("market", "US")
                current_price = data.get("current_price")
                change_pct = data.get("change_pct")
                ah_change_pct = data.get("ah_change_pct")
                ah_change_label = data.get("ah_change_label")
                sector = data.get("sector")
                week52_high = data.get("week52_high")
                week52_low = data.get("week52_low")
                week52_high_date = data.get("week52_high_date")
                week52_low_date = data.get("week52_low_date")
                drawdown = data.get("drawdown")
                distance_low_pct = data.get("distance_low_pct")
                pe_ratio = data.get("pe_ratio")
                market_status = data.get("market_status", "未知")
                last_updated = data.get("last_updated")

            cursor = db.execute(
                """INSERT INTO stocks
                   (ticker, name, market, threshold, current_price, change_pct, ah_change_pct, ah_change_label, sector,
                    week52_high, week52_low, week52_high_date, week52_low_date,
                    drawdown, distance_low_pct, pe_ratio, market_status, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ticker, name, market, threshold, current_price, change_pct, ah_change_pct, ah_change_label, sector,
                 week52_high, week52_low, week52_high_date, week52_low_date,
                 drawdown, distance_low_pct, pe_ratio, market_status, last_updated),
            )
            db.commit()

            return StockResponse(
                id=cursor.lastrowid,
                ticker=ticker,
                name=name,
                market=market,
                threshold=threshold,
                current_price=current_price,
                change_pct=change_pct,
                ah_change_pct=ah_change_pct,
                ah_change_label=ah_change_label,
                sector=sector,
                week52_high=week52_high,
                week52_low=week52_low,
                week52_high_date=week52_high_date,
                week52_low_date=week52_low_date,
                drawdown=drawdown,
                distance_low_pct=distance_low_pct,
                pe_ratio=pe_ratio,
                market_status=market_status,
                last_updated=last_updated,
            )
        finally:
            db.close()

    def update_stock(self, ticker: str, **kwargs) -> Optional[StockResponse]:
        """更新股票设置"""
        ticker = ticker.strip().upper()
        db = get_db()
        try:
            existing = db.execute("SELECT * FROM stocks WHERE ticker = ?", (ticker,)).fetchone()
            if not existing:
                return None

            updates = {}
            allowed_fields = ["name", "threshold", "current_price", "change_pct", "ah_change_pct", "ah_change_label", "sector",
                              "week52_high", "week52_low", "week52_high_date", "week52_low_date",
                              "drawdown", "distance_low_pct", "pe_ratio", "market_status"]
            for key, value in kwargs.items():
                if key in allowed_fields and value is not None:
                    updates[key] = value

            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                values = list(updates.values()) + [ticker]
                db.execute(f"UPDATE stocks SET {set_clause} WHERE ticker = ?", values)
                db.commit()

            row = db.execute("SELECT * FROM stocks WHERE ticker = ?", (ticker,)).fetchone()
            return self._row_to_response(row) if row else None
        finally:
            db.close()

    def delete_stock(self, ticker: str) -> bool:
        """删除股票"""
        ticker = ticker.strip().upper()
        db = get_db()
        try:
            cursor = db.execute("DELETE FROM stocks WHERE ticker = ?", (ticker,))
            db.commit()
            return cursor.rowcount > 0
        finally:
            db.close()

    def _fetch_one_stock(self, ticker: str) -> Optional[Dict[str, Any]]:
        """获取单只股票的实时数据并更新数据库"""
        data = DataFetcher.get_stock_info(ticker, self.api_key)
        if not data:
            return None

        # 禁止 demo 假数据覆盖数据库（仅刷新场景，新增股票不受影响）
        if data.get("source") == "demo":
            return data

        db = get_db()
        try:
            db.execute(
                """UPDATE stocks SET
                    name = ?, market = ?, current_price = ?, change_pct = ?, ah_change_pct = ?, ah_change_label = ?, sector = ?,
                    week52_high = ?, week52_low = ?, week52_high_date = ?, week52_low_date = ?,
                    drawdown = ?, distance_low_pct = ?, pe_ratio = ?, market_status = ?,
                    last_updated = ?
                   WHERE ticker = ?""",
                (
                    data.get("name"),
                    data.get("market"),
                    data.get("current_price"),
                    data.get("change_pct"),
                    data.get("ah_change_pct"),
                    data.get("ah_change_label"),
                    data.get("sector"),
                    data.get("week52_high"),
                    data.get("week52_low"),
                    data.get("week52_high_date"),
                    data.get("week52_low_date"),
                    data.get("drawdown"),
                    data.get("distance_low_pct"),
                    data.get("pe_ratio"),
                    data.get("market_status", "未知"),
                    data.get("last_updated"),
                    ticker,
                ),
            )
            db.commit()
            self._record_price_point(data)
            return data
        finally:
            db.close()

    def refresh_all(self) -> List[StockResponse]:
        """刷新所有股票数据（同步，保留向后兼容）"""
        db = get_db()
        try:
            rows = db.execute("SELECT ticker FROM stocks").fetchall()
        finally:
            db.close()

        for row in rows:
            self._fetch_one_stock(row["ticker"])

        return self.get_all_stocks()

    def start_refresh_all(self) -> dict:
        """启动后台刷新，返回 task_id 供轮询进度"""
        db = get_db()
        try:
            rows = db.execute("SELECT ticker FROM stocks").fetchall()
        finally:
            db.close()

        tickers = [row["ticker"] for row in rows]
        task_id = uuid.uuid4().hex[:8]

        with self._lock:
            self._refresh_tasks[task_id] = {
                "total": len(tickers),
                "done": 0,
                "current": "",
                "current_name": "",
                "status": "running",
                "error": None,
                "last_stock": None,
                "last_status": None,
            }

        thread = threading.Thread(
            target=self._refresh_all_bg,
            args=(task_id, tickers),
            daemon=True,
        )
        thread.start()
        return {"task_id": task_id, "total": len(tickers)}

    def get_refresh_progress(self, task_id: str) -> Optional[dict]:
        """查询刷新进度"""
        with self._lock:
            task = self._refresh_tasks.get(task_id)
            if task is None:
                return None
            return dict(task)

    def _refresh_all_bg(self, task_id: str, tickers: list):
        """后台线程：逐只刷新，每刷完一只将数据写入进度供前端实时更新"""
        try:
            for i, ticker in enumerate(tickers):
                current_stock = self.get_stock_by_ticker(ticker)
                with self._lock:
                    self._refresh_tasks[task_id]["current"] = ticker
                    self._refresh_tasks[task_id]["current_name"] = current_stock.name if current_stock else ticker

                result = self._fetch_one_stock(ticker)
                stock = self.get_stock_by_ticker(ticker)

                with self._lock:
                    self._refresh_tasks[task_id]["done"] = i + 1
                    if stock:
                        self._refresh_tasks[task_id]["last_stock"] = {
                            "ticker": stock.ticker,
                            "name": stock.name,
                            "market": stock.market,
                            "current_price": stock.current_price,
                            "change_pct": stock.change_pct,
                            "drawdown": stock.drawdown,
                            "week52_high": stock.week52_high,
                            "week52_low": stock.week52_low,
                            "pe_ratio": stock.pe_ratio,
                            "sector": stock.sector,
                            "market_status": stock.market_status,
                            "last_updated": stock.last_updated,
                        }
                        self._refresh_tasks[task_id]["last_status"] = "ok"
                    else:
                        self._refresh_tasks[task_id]["last_status"] = "fail"

            with self._lock:
                self._refresh_tasks[task_id]["status"] = "completed"
        except Exception as e:
            with self._lock:
                self._refresh_tasks[task_id]["status"] = "error"
                self._refresh_tasks[task_id]["error"] = str(e)

    def refresh_one(self, ticker: str) -> Optional[StockResponse]:
        """刷新单只股票，返回更新后的数据；失败返回 None"""
        ticker = ticker.strip().upper()
        data = self._fetch_one_stock(ticker)
        if data:
            return self.get_stock_by_ticker(ticker)
        return None

    def refresh_one_with_status(self, ticker: str) -> dict:
        """刷新单只股票，返回 {success, stock, error} 供前端展示"""
        ticker = ticker.strip().upper()
        data = self._fetch_one_stock(ticker)
        if data:
            stock = self.get_stock_by_ticker(ticker)
            return {"success": True, "stock": stock, "error": None}
        return {"success": False, "stock": None, "error": "数据获取失败，请检查网络或 API Key"}

    # ── 历史行情落库（price_history）──────────────────────────

    @staticmethod
    def _price_bucket(dt: datetime) -> str:
        """北京时间 → 15 分钟桶 'YYYY-MM-DD HH:MM'（回撤趋势图的采样粒度）"""
        return dt.strftime("%Y-%m-%d %H:") + f"{dt.minute // 15 * 15:02d}"

    def _record_price_point(self, data: Optional[Dict[str, Any]]) -> None:
        """真实行情落库 price_history（15 分钟桶幂等，demo 数据不落库）"""
        if not data or data.get("source") == "demo":
            return
        now = datetime.now(timezone(timedelta(hours=8)))
        retention_days = int(os.environ.get("PRICE_HISTORY_RETENTION_DAYS", "90"))
        cutoff = (now - timedelta(days=retention_days)).isoformat()
        db = get_db()
        try:
            db.execute(
                """INSERT OR REPLACE INTO price_history
                   (ticker, market, name, bucket, current_price, change_pct, drawdown, week52_high, captured_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.get("ticker"),
                    data.get("market"),
                    data.get("name"),
                    self._price_bucket(now),
                    data.get("current_price"),
                    data.get("change_pct"),
                    data.get("drawdown"),
                    data.get("week52_high"),
                    now.isoformat(),
                ),
            )
            # 惰性清理过期行（保留策略默认 90 天）
            db.execute("DELETE FROM price_history WHERE captured_at < ?", (cutoff,))
            db.commit()
        finally:
            db.close()

    def get_price_history(self, ticker: str, days: int = 30) -> dict:
        """查询单只股票的历史行情序列（升序），供趋势图使用"""
        ticker = ticker.strip().upper()
        days = max(1, min(int(days), 90))
        cutoff = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=days)).isoformat()
        db = get_db()
        try:
            rows = db.execute(
                """SELECT bucket, market, captured_at, current_price, change_pct, drawdown, week52_high
                   FROM price_history WHERE ticker = ? AND captured_at >= ?
                   ORDER BY bucket ASC""",
                (ticker, cutoff),
            ).fetchall()
        finally:
            db.close()
        points = [dict(r) for r in rows]
        market = points[0]["market"] if points else None
        return {"ticker": ticker, "market": market, "days": days, "points": points}