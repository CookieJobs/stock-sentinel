"""数据库初始化与连接管理"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "sentinel.db"


def get_db() -> sqlite3.Connection:
    """获取数据库连接"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    """初始化数据库表结构和默认设置"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    cursor = db.cursor()

    # 创建设置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # 创建股票表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'US',
            threshold REAL NOT NULL DEFAULT 15.0,
            alert_enabled INTEGER NOT NULL DEFAULT 0,
            current_price REAL,
            change_pct REAL,
            sector TEXT,
            week52_high REAL,
            week52_low REAL,
            week52_high_date TEXT,
            week52_low_date TEXT,
            drawdown REAL,
            distance_low_pct REAL,
            pe_ratio REAL,
            market_status TEXT DEFAULT '未知',
            ah_change_pct REAL,
            ah_change_label TEXT,
            last_updated TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # 默认设置
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('theme', 'dark')")

    # 迁移：添加后期新增的列
    try:
        cursor.execute("ALTER TABLE stocks ADD COLUMN change_pct REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE stocks ADD COLUMN distance_low_pct REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE stocks ADD COLUMN sector TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE stocks ADD COLUMN alert_enabled INTEGER")
        # 旧版本以负数代表启用、0 代表关闭；只在新增列的这一次转换。
        cursor.execute(
            "UPDATE stocks SET alert_enabled = CASE WHEN threshold < 0 THEN 1 ELSE 0 END"
        )
        cursor.execute("UPDATE stocks SET threshold = ABS(threshold)")
    except sqlite3.OperationalError:
        pass

    # 告警表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            sent_date TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, sent_date)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_unread (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT, market TEXT, drawdown_pct REAL, threshold REAL,
            current_price REAL, week52_high REAL, week52_high_date TEXT,
            event_type TEXT NOT NULL DEFAULT 'breach',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE alert_unread ADD COLUMN event_type TEXT NOT NULL DEFAULT 'breach'")
    except sqlite3.OperationalError:
        pass
    for column in (
        "event_type TEXT NOT NULL DEFAULT 'breach'",
        "drawdown_pct REAL",
        "threshold REAL",
    ):
        try:
            cursor.execute(f"ALTER TABLE alert_history ADD COLUMN {column}")
        except sqlite3.OperationalError:
            pass
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_state (
            ticker TEXT PRIMARY KEY,
            is_breached INTEGER NOT NULL DEFAULT 0,
            last_drawdown REAL,
            breached_at TIMESTAMP,
            recovered_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 每日简报：股票快照（供简报做"昨今对比"）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT,
            current_price REAL,
            change_pct REAL,
            drawdown REAL,
            week52_high REAL,
            threshold REAL,
            UNIQUE(snapshot_date, ticker)
        )
    """)

    # 每日简报：简报记录（每天一条，LLM 或模板生成）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS briefings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            briefing_date TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'template',
            stats TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 历史行情：高频连续采样（回撤趋势图数据源，15 分钟桶幂等）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            market TEXT,
            name TEXT,
            bucket TEXT NOT NULL,          -- 北京时间 YYYY-MM-DD HH:MM，对齐 15 分钟
            current_price REAL,
            change_pct REAL,
            drawdown REAL,
            week52_high REAL,
            captured_at TEXT NOT NULL,     -- ISO 时间戳（北京时间）
            UNIQUE(ticker, bucket)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_ticker ON price_history(ticker, bucket)")

    db.commit()
    db.close()
