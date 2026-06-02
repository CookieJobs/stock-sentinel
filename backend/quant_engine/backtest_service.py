"""回测服务 — 异步运行回测 + 持久化到 backtests 表

- submit(): 提交回测任务（返回 backtest_id）
- 异步线程跑回测（不阻塞 API）
- 进度：pending → running → done / error
- 结果：写入 metrics / equity_curve / trades
- fetch(): 获取回测结果
- list_recent(): 列出最近 N 个回测
"""
from __future__ import annotations
import json
import logging
import threading
from datetime import datetime
from typing import Optional

import pandas as pd

from .db import get_quant_db
from .backtest import run_backtest, SIGNAL_REGISTRY
from .kline_service import get_or_fetch, get_kline_meta
from .risk import compute_all

logger = logging.getLogger(__name__)


# ── 提交 ──────────────────────────────────────────────────────

def submit(
    *,
    name: str,
    strategy: str,
    params: dict,
    tickers: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000,
    commission: float = 0.0003,
    slippage: float = 0.001,
    benchmark: str = "000300.SH",
    market: str = "CN",
    rebalance_freq: str = "monthly",
) -> int:
    """提交回测任务，返回 backtest_id

    Args:
        strategy: equal_weight / ma_cross / factor_rank
        tickers: 股票代码列表
        market: CN / HK / US（决定涨跌停规则）
    """
    if strategy not in SIGNAL_REGISTRY:
        raise ValueError(f"Unknown strategy: {strategy}. Available: {list(SIGNAL_REGISTRY)}")
    if not tickers:
        raise ValueError("tickers 不能为空")

    db = get_quant_db()
    try:
        cur = db.execute(
            """INSERT INTO backtests
               (name, strategy, params, start_date, end_date,
                initial_capital, commission, slippage, benchmark, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (name, strategy, json.dumps(params), start_date, end_date,
             initial_capital, commission, slippage, benchmark),
        )
        backtest_id = cur.lastrowid
        db.commit()
    finally:
        db.close()

    # 起后台线程跑回测
    thread = threading.Thread(
        target=_run_backtest_bg,
        args=(backtest_id, tickers, market, rebalance_freq),
        daemon=True,
    )
    thread.start()
    return backtest_id


def _run_backtest_bg(backtest_id: int, tickers: list[str], market: str, rebalance_freq: str):
    """后台线程：拉 K 线 → 跑回测 → 写结果"""
    try:
        _update_status(backtest_id, "running")
        _set_progress(backtest_id, current=f"加载 {len(tickers)} 只股票 K 线", done=0, total=len(tickers))

        # 0. 读 benchmark 字段（用于基准 K 线）
        db = get_quant_db()
        try:
            row_bench = db.execute("SELECT benchmark FROM backtests WHERE id = ?", (backtest_id,)).fetchone()
        finally:
            db.close()
        benchmark = row_bench["benchmark"] if row_bench else "000300.SH"

        # 1. 拉所有 tickers 的 K 线
        all_klines = []
        failed = []
        for i, ticker in enumerate(tickers):
            try:
                df = get_or_fetch(ticker, market, period="1d", adj="qfq")
                if df is None or df.empty:
                    failed.append(ticker)
                    continue
                df = df.copy()
                df["ticker"] = ticker
                all_klines.append(df)
            except Exception as e:
                logger.warning("Failed to fetch kline for %s: %s", ticker, e)
                failed.append(ticker)
            _set_progress(backtest_id, current=ticker, done=i + 1, total=len(tickers))

        if not all_klines:
            _update_status(backtest_id, "error", error_msg="所有 ticker K 线拉取失败")
            return

        prices = pd.concat(all_klines, ignore_index=True)

        # 2. 拉基准 K 线（失败则用第一只 ticker 作 fallback）
        benchmark_data = None
        benchmark_ticker, benchmark_market = _resolve_benchmark(benchmark)
        for tk, mk in [(benchmark_ticker, benchmark_market), (tickers[0], market), ("000300", "CN")]:
            try:
                bench_df = get_or_fetch(tk, mk, period="1d", adj="qfq")
                if bench_df is not None and not bench_df.empty and "close" in bench_df.columns:
                    benchmark_data = bench_df[["trade_date", "close"]].copy()
                    logger.info("Benchmark kline loaded: %s/%s, %d rows", tk, mk, len(benchmark_data))
                    break
            except Exception as e:
                logger.warning("Benchmark kline fetch failed for %s/%s: %s", tk, mk, e)
                continue

        if benchmark_data is None or benchmark_data.empty:
            logger.warning("All benchmark sources failed; building mock benchmark from price target")
            # 兜底：用 prices 中第一只 ticker 的 close 作为伪基准
            benchmark_data = prices[["trade_date", "close"]].drop_duplicates(subset=["trade_date"]).copy()
            benchmark_data = benchmark_data.rename(columns={"close": "close"})

        # 3. 读回测参数
        db = get_quant_db()
        try:
            row = db.execute(
                "SELECT * FROM backtests WHERE id = ?", (backtest_id,)
            ).fetchone()
        finally:
            db.close()
        if not row:
            _update_status(backtest_id, "error", error_msg="回测任务不存在")
            return
        strategy = row["strategy"]
        params = json.loads(row["params"]) if row["params"] else {}
        signal_fn = SIGNAL_REGISTRY[strategy]["fn"]
        start_date = row["start_date"]
        end_date = row["end_date"]
        initial_capital = row["initial_capital"]
        commission = row["commission"]
        slippage = row["slippage"]

        # 4. 跑回测
        _set_progress(backtest_id, current="回测计算中...", done=len(tickers), total=len(tickers))
        result = run_backtest(
            prices=prices,
            benchmark=benchmark_data,
            signal_fn=signal_fn,
            signal_params=params,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage,
            rebalance_freq=rebalance_freq,
            market=market,
        )

        if result.error:
            _update_status(backtest_id, "error", error_msg=result.error)
            return

        # 5. 算风险指标（用 risk.py）
        risk_metrics = compute_all(result.equity_curve, initial_capital)
        # 合并（回测引擎算的 metrics + risk.py 算的，更全）
        merged_metrics = {**result.metrics, **risk_metrics}

        # 6. 写回 DB
        db = get_quant_db()
        try:
            db.execute(
                """UPDATE backtests SET
                    status = 'done',
                    metrics = ?,
                    equity_curve = ?,
                    trades = ?,
                    completed_at = ?
                   WHERE id = ?""",
                (
                    json.dumps(merged_metrics, default=str),
                    json.dumps(result.equity_curve, default=str),
                    json.dumps(result.trades, default=str),
                    datetime.now().isoformat(),
                    backtest_id,
                ),
            )
            db.commit()
        finally:
            db.close()
        logger.info("Backtest %d done: total_return=%.4f, sharpe=%.2f",
                    backtest_id, merged_metrics.get("total_return", 0), merged_metrics.get("sharpe", 0))
    except Exception as e:
        logger.exception("Backtest %d failed", backtest_id)
        _update_status(backtest_id, "error", error_msg=str(e))


def _update_status(backtest_id: int, status: str, error_msg: Optional[str] = None):
    db = get_quant_db()
    try:
        if error_msg:
            db.execute(
                "UPDATE backtests SET status = ?, error_msg = ? WHERE id = ?",
                (status, error_msg, backtest_id),
            )
        else:
            db.execute(
                "UPDATE backtests SET status = ? WHERE id = ?", (status, backtest_id)
            )
        db.commit()
    finally:
        db.close()


def _set_progress(backtest_id: int, *, current: str, done: int, total: int):
    """写进度（v1: 只写 current text 到 status 行后面）"""
    db = get_quant_db()
    try:
        db.execute(
            "UPDATE backtests SET error_msg = COALESCE(?, error_msg) WHERE id = ?",
            (f"[{done}/{total}] {current}", backtest_id),
        )
        db.commit()
    finally:
        db.close()


def _resolve_benchmark(code: str) -> tuple[str, str]:
    """基准代码 → (ticker, market)"""
    if code.startswith(("000", "399", "60", "30")):  # A 股
        return code.split(".")[0], "CN"
    if code in ("HSI",):  # 恒生
        return "HSI", "HK"
    if code in ("SPX", "NDX", "DJI"):  # 美股
        return code, "US"
    return code, "CN"


# ── 查询 ──────────────────────────────────────────────────────

def fetch(backtest_id: int) -> Optional[dict]:
    """获取回测任务详情 + 结果"""
    db = get_quant_db()
    try:
        row = db.execute("SELECT * FROM backtests WHERE id = ?", (backtest_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        # 解析 JSON 字段
        for k in ("params", "metrics", "equity_curve", "trades"):
            if result.get(k):
                try:
                    result[k] = json.loads(result[k])
                except (json.JSONDecodeError, TypeError):
                    result[k] = None
        return result
    finally:
        db.close()


def list_recent(limit: int = 20) -> list[dict]:
    """列出最近 N 个回测（按 id 倒序）"""
    db = get_quant_db()
    try:
        rows = db.execute(
            "SELECT id, name, strategy, status, start_date, end_date, "
            "       created_at, completed_at FROM backtests ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()
