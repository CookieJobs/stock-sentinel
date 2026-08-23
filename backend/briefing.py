"""每日简报 — 聚合监控数据 + LLM 生成中文简报（无 Key 时模板兜底）

流程: 采集当日快照 → 组装上下文(含昨日对比) → LLM 或模板生成 → 落库 briefings
调度: BriefingScheduler 每 60s 检查一次，北京时间到点且当日未生成则触发。
"""
import json
import logging
import os
import threading
import requests
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import get_db

logger = logging.getLogger(__name__)

# 北京时间
_BJ = timezone(timedelta(hours=8))

# ── 配置 ──────────────────────────────────────────────────────
BRIEFING_ENABLED = os.environ.get("BRIEFING_ENABLED", "true").lower() == "true"
BRIEFING_TIME = os.environ.get("BRIEFING_TIME", "08:30")   # 北京时间 HH:MM
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")

DISCLAIMER = "本简报由 AI 自动生成，仅供信息参考，不构成投资建议。"

_CURRENCY = {"CN": "¥", "HK": "HK$", "US": "$"}


def _currency(market: Optional[str]) -> str:
    return _CURRENCY.get(market or "", "$")


def now_beijing() -> datetime:
    return datetime.now(_BJ)


def today_beijing() -> str:
    return now_beijing().strftime("%Y-%m-%d")


# ── 存取辅助 ──────────────────────────────────────────────────

def list_briefings(limit: int = 30) -> List[dict]:
    """简报历史列表（不含全文）"""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, briefing_date, title, mode, created_at FROM briefings "
            "ORDER BY briefing_date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def get_latest_briefing() -> Optional[dict]:
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM briefings ORDER BY briefing_date DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def get_briefing(briefing_id: int) -> Optional[dict]:
    db = get_db()
    try:
        row = db.execute("SELECT * FROM briefings WHERE id = ?", (briefing_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def has_briefing_on(date: str) -> bool:
    db = get_db()
    try:
        row = db.execute("SELECT 1 FROM briefings WHERE briefing_date = ?", (date,)).fetchone()
        return row is not None
    finally:
        db.close()


# ── 生成器 ────────────────────────────────────────────────────

class BriefingGenerator:
    """每日简报生成器 — 快照采集 + 上下文组装 + LLM/模板生成"""

    def collect_snapshot(self, date: str):
        """将 stocks 全表写入当日快照（幂等，REPLACE）"""
        db = get_db()
        try:
            rows = db.execute(
                "SELECT ticker, name, market, current_price, change_pct, drawdown, week52_high, threshold FROM stocks"
            ).fetchall()
            for r in rows:
                db.execute(
                    """INSERT OR REPLACE INTO stock_snapshots
                       (snapshot_date, ticker, name, market, current_price, change_pct, drawdown, week52_high, threshold)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (date, r["ticker"], r["name"], r["market"], r["current_price"],
                     r["change_pct"], r["drawdown"], r["week52_high"], r["threshold"]),
                )
            db.commit()
            return len(rows)
        finally:
            db.close()

    def load_previous_snapshot(self, date: str):
        """加载 date 之前最新一天的快照，返回 (prev_date, {ticker: row})；无则 (None, None)"""
        db = get_db()
        try:
            row = db.execute(
                "SELECT MAX(snapshot_date) AS d FROM stock_snapshots WHERE snapshot_date < ?",
                (date,),
            ).fetchone()
            if not row or not row["d"]:
                return None, None
            rows = db.execute(
                "SELECT * FROM stock_snapshots WHERE snapshot_date = ?", (row["d"],)
            ).fetchall()
            return row["d"], {r["ticker"]: dict(r) for r in rows}
        finally:
            db.close()

    def _load_trends(self, tickers: List[str], date: str, days: int = 30) -> List[dict]:
        """读取 price_history 回撤序列，供简报前端渲染 sparkline（点数不足 2 的过滤）"""
        if not tickers:
            return []
        date_dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=_BJ)
        cutoff = (date_dt - timedelta(days=days)).isoformat()
        ph = ",".join("?" * len(tickers))
        db = get_db()
        try:
            rows = db.execute(
                f"""SELECT ticker, name, market, drawdown
                    FROM price_history
                    WHERE ticker IN ({ph}) AND captured_at >= ?
                    ORDER BY ticker, bucket ASC""",
                (*tickers, cutoff),
            ).fetchall()
        finally:
            db.close()
        by_ticker: Dict[str, dict] = {}
        for r in rows:
            d = by_ticker.setdefault(r["ticker"], {
                "ticker": r["ticker"], "name": r["name"], "market": r["market"], "points": [],
            })
            if r["drawdown"] is not None:
                d["points"].append(r["drawdown"])
        order = {t: i for i, t in enumerate(tickers)}
        trends = [d for d in by_ticker.values() if len(d["points"]) >= 2]
        trends.sort(key=lambda d: order.get(d["ticker"], 999))
        return trends

    def build_context(self, date: str, prev: Optional[Dict[str, dict]], prev_date: Optional[str] = None) -> Dict[str, Any]:
        """组装简报所需的全部结构化数据"""
        db = get_db()
        try:
            rows = db.execute(
                "SELECT * FROM stocks ORDER BY ticker"
            ).fetchall()
        finally:
            db.close()

        stocks = [dict(r) for r in rows]
        with_dd = [s for s in stocks if s.get("drawdown") is not None]
        avg_dd = round(sum(s["drawdown"] for s in with_dd) / len(with_dd), 2) if with_dd else None

        market_count = {"US": 0, "CN": 0, "HK": 0}
        for s in stocks:
            market_count[s.get("market") or "US"] = market_count.get(s.get("market") or "US", 0) + 1

        # 超阈值清单（threshold < 0 且 |drawdown| >= |threshold|）
        over_threshold = [
            s for s in stocks
            if s.get("drawdown") is not None and s.get("threshold") is not None
            and s["threshold"] < 0 and abs(s["drawdown"]) >= abs(s["threshold"])
        ]

        # 回撤最深 Top 5
        top_drawdowns = sorted(with_dd, key=lambda s: s["drawdown"])[:5]

        # 今日涨跌幅 Top
        with_chg = [s for s in stocks if s.get("change_pct") is not None]
        top_gainers = sorted(with_chg, key=lambda s: s["change_pct"], reverse=True)[:3]
        top_losers = sorted(with_chg, key=lambda s: s["change_pct"])[:3]

        # 与上一份快照对比：回撤变化 >= 1pp 的股票，按变化幅度排序
        changes = []
        if prev:
            for s in stocks:
                old = prev.get(s["ticker"])
                if not old or old.get("drawdown") is None or s.get("drawdown") is None:
                    continue
                delta = round(s["drawdown"] - old["drawdown"], 2)
                if abs(delta) >= 1.0:
                    changes.append({
                        "ticker": s["ticker"], "name": s["name"], "market": s["market"],
                        "prev_drawdown": old["drawdown"], "drawdown": s["drawdown"],
                        "delta": delta,
                    })
            changes.sort(key=lambda c: abs(c["delta"]), reverse=True)
            changes = changes[:8]

        return {
            "date": date,
            "prev_date": prev_date,
            "total": len(stocks),
            "market_count": market_count,
            "avg_drawdown": avg_dd,
            "over_threshold": [
                {"ticker": s["ticker"], "name": s["name"], "market": s["market"],
                 "drawdown": s["drawdown"], "threshold": s["threshold"]}
                for s in over_threshold
            ],
            "top_drawdowns": [
                {"ticker": s["ticker"], "name": s["name"], "market": s["market"],
                 "drawdown": s["drawdown"], "current_price": s["current_price"],
                 "week52_high": s["week52_high"]}
                for s in top_drawdowns
            ],
            "top_gainers": [
                {"ticker": s["ticker"], "name": s["name"], "change_pct": s["change_pct"]}
                for s in top_gainers
            ],
            "top_losers": [
                {"ticker": s["ticker"], "name": s["name"], "change_pct": s["change_pct"]}
                for s in top_losers
            ],
            "changes": changes,
        }

    # ── LLM 调用 ──────────────────────────────────────────────

    def _call_llm(self, system: str, user: str) -> Optional[str]:
        """调用 OpenAI 兼容 chat/completions 接口；任何失败返回 None（不抛异常）"""
        if not LLM_API_KEY:
            return None
        url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1200,
                },
                timeout=60,
            )
            if resp.status_code != 200:
                logger.warning("LLM call failed: HTTP %s body=%s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip() if content else None
        except Exception:
            logger.warning("LLM call exception", exc_info=True)
            return None

    # ── 模板生成 ──────────────────────────────────────────────

    def generate_template(self, ctx: Dict[str, Any]) -> str:
        d = ctx["date"]
        mc = ctx["market_count"]
        lines = [f"# 📰 StockSentinel 每日简报（{d}）", ""]

        # 组合概况
        lines.append("## 📊 组合概况")
        if ctx["total"] == 0:
            lines.append("- 暂无监控数据，请先在 Dashboard 添加股票。")
        else:
            avg = f"{ctx['avg_drawdown']:.2f}%" if ctx["avg_drawdown"] is not None else "--"
            lines.append(
                f"- 监控 {ctx['total']} 只：美股 {mc.get('US', 0)} / A股 {mc.get('CN', 0)} / 港股 {mc.get('HK', 0)}；平均回撤 {avg}"
            )
            lines.append(f"- 超过回撤阈值的股票：{len(ctx['over_threshold'])} 只")
            if ctx["over_threshold"]:
                for s in ctx["over_threshold"][:10]:
                    lines.append(
                        f"  - {s['ticker']} {s['name'] or ''}（{s['market']}）回撤 {s['drawdown']:.2f}% / 阈值 {abs(s['threshold']):.2f}%"
                    )
        lines.append("")

        # 回撤最深
        lines.append("## 🔻 回撤最深的股票")
        if ctx["top_drawdowns"]:
            for i, s in enumerate(ctx["top_drawdowns"], 1):
                cur = f"{_currency(s['market'])}{s['current_price']:.2f}" if s["current_price"] is not None else "--"
                high = f"{_currency(s['market'])}{s['week52_high']:.2f}" if s["week52_high"] is not None else "--"
                lines.append(f"{i}. {s['ticker']} {s['name'] or ''}（{s['market']}）回撤 {s['drawdown']:.2f}%，现价 {cur}，52W高 {high}")
        else:
            lines.append("- 无数据")
        lines.append("")

        # 今日异动
        lines.append("## ⚡ 今日异动")
        if ctx["top_gainers"]:
            g = "、".join(f"{s['ticker']} +{s['change_pct']:.2f}%" for s in ctx["top_gainers"])
            lines.append(f"- 涨幅最大：{g}")
        if ctx["top_losers"]:
            l = "、".join(f"{s['ticker']} {s['change_pct']:.2f}%" for s in ctx["top_losers"])
            lines.append(f"- 跌幅最大：{l}")
        if ctx["changes"]:
            lines.append("- 较上一份简报回撤变化明显的股票：")
            for c in ctx["changes"][:8]:
                arrow = "扩大" if c["delta"] < 0 else "收窄"
                lines.append(
                    f"  - {c['ticker']} {c['name'] or ''}：回撤 {c['prev_drawdown']:.2f}% → {c['drawdown']:.2f}%（{arrow} {abs(c['delta']):.2f}pp）"
                )
        else:
            lines.append("- 无明显异动或暂无对比数据")
        lines.append("")

        # 异动归因（同花顺官方）
        if ctx.get("anomalies"):
            lines.append("## ⚡ 今日异动归因（同花顺）")
            for a in ctx["anomalies"][:10]:
                reason = a.get("reason") or "暂无解读"
                lines.append(f"- {a['ticker']} {a.get('name') or ''}（{a.get('tag')}）：{reason}")
            lines.append("")

        # 风险与免责
        lines.append("## ⚠️ 风险提醒")
        lines.append(f"- 超过阈值的股票请关注是否触发告警；回撤扩大趋势需留意基本面前景。")
        lines.append(f"- {DISCLAIMER}")
        return "\n".join(lines)

    # ── 入口 ──────────────────────────────────────────────────

    def generate(self, date: Optional[str] = None) -> dict:
        """生成当日简报并落库，返回 {briefing, mode}"""
        date = date or today_beijing()
        self.collect_snapshot(date)
        prev_date, prev = self.load_previous_snapshot(date)
        ctx = self.build_context(date, prev, prev_date)

        # 回撤趋势（只进 stats 供前端渲染，不进 LLM 上下文省 token）
        trends = self._load_trends([s["ticker"] for s in ctx["top_drawdowns"]], date, days=30)

        # 异动归因：同花顺官方当日异动原因（监控股票），先拉再查
        anomalies = []
        try:
            from quant_engine import ths_service
            ths_service.fetch_anomalies()
            monitored = ths_service.get_monitored_tickers()
            anomalies = ths_service.get_anomalies(tickers=monitored or None, limit=50)
        except Exception as e:
            logger.warning("Briefing anomaly enrichment failed: %s", e)
        ctx["anomalies"] = anomalies

        mode = "template"
        content = self.generate_template(ctx)

        if LLM_API_KEY:
            system = (
                "你是 StockSentinel 的个人投研助手。你只会获得一份结构化 JSON 监控数据。"
                "请用简体中文输出一份 markdown 简报，分「组合概况 / 重点异动 / 风险提醒」三节；"
                "只依据给定数据，不编造任何数字；"
                f"文末必须包含免责声明：{DISCLAIMER}"
            )
            user = (
                f"以下是 {date} 的监控数据（JSON）：\n```json\n{json.dumps(ctx, ensure_ascii=False)}\n```\n"
                "请生成简报。要求：重点突出回撤扩大、新超过阈值、大跌的个股；"
                "若无明显变化请如实说明；数据为空的项不要臆造。"
            )
            llm_content = self._call_llm(system, user)
            if llm_content:
                mode = "llm"
                content = llm_content
                # 兜底：LLM 输出缺失免责声明时强制追加
                if DISCLAIMER not in content:
                    content = content.rstrip() + f"\n\n{DISCLAIMER}"
            else:
                logger.info("LLM unavailable, using template mode for %s", date)

        title = f"📰 StockSentinel 每日简报（{date}）"
        stats = {**ctx, "trends": trends}
        db = get_db()
        try:
            db.execute(
                """INSERT OR REPLACE INTO briefings (briefing_date, title, content, mode, stats)
                   VALUES (?, ?, ?, ?, ?)""",
                (date, title, content, mode, json.dumps(stats, ensure_ascii=False)),
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM briefings WHERE briefing_date = ?", (date,)
            ).fetchone()
            briefing = dict(row) if row else None
        finally:
            db.close()
        return {"briefing": briefing, "mode": mode}


# ── 调度器 ────────────────────────────────────────────────────

class BriefingScheduler:
    """定时触发每日简报 — 每 60s 检查一次，北京时间到点且当日未生成则生成"""

    def __init__(self):
        self.generator = BriefingGenerator()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._interval = 60

    def _parse_time(self) -> timedelta:
        """解析 BRIEFING_TIME（HH:MM）为当天相对午夜的 timedelta；非法时回退 08:30"""
        try:
            h, m = BRIEFING_TIME.strip().split(":")
            return timedelta(hours=int(h), minutes=int(m))
        except Exception:
            logger.warning("Invalid BRIEFING_TIME=%r, fallback 08:30", BRIEFING_TIME)
            return timedelta(hours=8, minutes=30)

    def start(self):
        if not BRIEFING_ENABLED:
            logger.info("Daily briefing disabled (BRIEFING_ENABLED != true)")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Briefing scheduler started, time=%s (Beijing)", BRIEFING_TIME)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            try:
                now = now_beijing()
                delta = self._parse_time()
                target = now.replace(hour=0, minute=0, second=0, microsecond=0) + delta
                date = now.strftime("%Y-%m-%d")
                if now >= target and not has_briefing_on(date):
                    logger.info("Daily briefing triggered at %s", now.isoformat())
                    self.generator.generate(date)
            except Exception:
                logger.exception("Briefing scheduler check failed")
            self._stop.wait(self._interval)
