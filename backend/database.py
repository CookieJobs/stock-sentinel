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
            threshold REAL NOT NULL DEFAULT 0.0,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.commit()
    db.close()
