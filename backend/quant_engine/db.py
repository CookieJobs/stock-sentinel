"""量化引擎数据库 — 扩展自 backend.database.py

新增 6 张表：
- kline              : K 线 OHLCV（多市场 / 多周期 / 复权）
- daily_metrics      : 日频估值/财务指标（PE/PB/ROE/ROA/增速/毛利率/...）
- factor_values      : 自研/多因子模型中间值（含截面排名）
- portfolios         : 组合
- portfolio_holdings : 组合持仓
- backtests          : 回测任务 / 结果（参数 / 指标 / 净值曲线 / 交易记录）

主键策略：所有表都 AUTOINCREMENT，UNIQUE 约束在 (ticker, date) / (portfolio_id, ticker) 等业务键上。
"""
import sqlite3
import logging
from pathlib import Path

from database import DB_PATH

logger = logging.getLogger(__name__)


# ── Schema 定义 ────────────────────────────────────────────────

SCHEMA = [
    # K 线：多市场、多周期、复权
    """
    CREATE TABLE IF NOT EXISTS kline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        market TEXT NOT NULL,                -- US / CN / HK
        period TEXT NOT NULL,                -- 1d / 1w / 1mo / 60m / 30m / 15m / 5m / 1m
        adj TEXT NOT NULL DEFAULT 'qfq',     -- qfq (前复权) / hfq (后复权) / none (不复权)
        trade_date TEXT NOT NULL,            -- YYYY-MM-DD 或 YYYY-MM-DD HH:MM
        open REAL, high REAL, low REAL, close REAL,
        volume REAL, amount REAL,
        UNIQUE(ticker, market, period, adj, trade_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_kline_lookup ON kline(ticker, market, period, adj, trade_date)",

    # 日频估值/财务指标（Tushare / AkShare / BaoStock 入库）
    """
    CREATE TABLE IF NOT EXISTS daily_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        name TEXT,                              -- 股票名称（BaoStock 提供）
        industry TEXT,                          -- 申万行业（BaoStock 提供）
        pe_ttm REAL, pb REAL, ps_ttm REAL, peg REAL,
        market_cap REAL, turnover_rate REAL,
        roe REAL, roa REAL,
        revenue_yoy REAL, profit_yoy REAL,
        gross_margin REAL, net_margin REAL,
        debt_ratio REAL, free_cash_flow REAL,
        UNIQUE(ticker, trade_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_daily_metrics ON daily_metrics(ticker, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_daily_metrics_industry ON daily_metrics(industry) WHERE industry IS NOT NULL",

    # 因子值（含截面分位排名）
    """
    CREATE TABLE IF NOT EXISTS factor_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        factor_name TEXT NOT NULL,           -- e.g. 'pe_ttm' / 'momentum_20d' / 'quality_roe'
        factor_value REAL,
        factor_rank INTEGER,                 -- 截面分位 (1 = 最高)
        UNIQUE(ticker, trade_date, factor_name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_factor_values ON factor_values(factor_name, trade_date, factor_rank)",

    # 组合
    """
    CREATE TABLE IF NOT EXISTS portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        benchmark TEXT DEFAULT '000300.SH',  -- 默认沪深 300
        rebalance_freq TEXT DEFAULT 'monthly',  -- monthly / quarterly / none
        created_at TEXT DEFAULT (datetime('now'))
    )
    """,

    # 组合持仓
    """
    CREATE TABLE IF NOT EXISTS portfolio_holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        market TEXT NOT NULL DEFAULT 'CN',
        weight REAL NOT NULL,                 -- 0-1
        added_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
        UNIQUE(portfolio_id, ticker)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_holdings ON portfolio_holdings(portfolio_id)",

    # 回测任务 + 结果
    """
    CREATE TABLE IF NOT EXISTS backtests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        portfolio_id INTEGER,
        strategy TEXT NOT NULL,               -- manual / ma_cross / momentum / factor_rank
        params TEXT,                          -- JSON: 策略参数
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        initial_capital REAL DEFAULT 1000000,
        commission REAL DEFAULT 0.0003,       -- 万三
        slippage REAL DEFAULT 0.001,          -- 千一
        benchmark TEXT DEFAULT '000300.SH',
        status TEXT DEFAULT 'pending',        -- pending / running / done / error
        error_msg TEXT,
        metrics TEXT,                         -- JSON: 收益/夏普/回撤 等
        equity_curve TEXT,                    -- JSON: [{date, value, benchmark_value}, ...]
        trades TEXT,                          -- JSON: [{date, ticker, side, price, qty, ...}, ...]
        created_at TEXT DEFAULT (datetime('now')),
        completed_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_backtests_status ON backtests(status, created_at DESC)",
]


# ── 连接管理 ────────────────────────────────────────────────────

def get_quant_db() -> sqlite3.Connection:
    """获取量化引擎数据库连接（共享 backend.database 的 DB 文件）"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_quant_db():
    """初始化量化引擎所需的表（幂等）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    try:
        cur = db.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        db.commit()
        logger.info("quant_engine DB schema initialized (%d stmts)", len(SCHEMA))
    finally:
        db.close()
