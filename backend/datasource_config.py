"""数据源选择配置 — settings 表持久化（key: datasource.<domain>）

数据域与可选源：
- realtime: auto / eastmoney / tencent（CN/HK 实时行情；美股恒为 finnhub）
- factor:   auto / tushare / ths / eastmoney_delay / baostock / akshare
- kline:    auto / ths / akshare / baostock / eastmoney（CN）

生效语义：钉住的源**排到链首优先尝试**，失败仍按原链降级（不锁死单源）。
"""
import logging
import sqlite3
from typing import Dict, List, Optional

from database import get_db

logger = logging.getLogger(__name__)

DOMAINS = ("realtime", "factor", "kline")

# 数据源中文名（括号英文名）——前端展示用
SOURCE_LABELS: Dict[str, str] = {
    "eastmoney": "东方财富 (eastmoney)",
    "tencent": "腾讯行情 (tencent)",
    "ths": "同花顺 (ths)",
    "tushare": "Tushare (tushare)",
    "eastmoney_delay": "东方财富延时 (eastmoney_delay)",
    "baostock": "BaoStock (baostock)",
    "akshare": "AkShare (akshare)",
    "finnhub": "Finnhub (finnhub)",
    "yahoo": "Yahoo Finance (yahoo)",
}

OPTIONS: Dict[str, List[str]] = {
    "realtime": ["eastmoney", "tencent"],
    "factor": ["tushare", "ths", "eastmoney_delay", "baostock", "akshare"],
    "kline": ["ths", "akshare", "baostock", "eastmoney"],
}


def label_of(source: str) -> str:
    """源名 → 中文名（括号英文名）；未知源回退源名本身"""
    return SOURCE_LABELS.get(source, source)


def _key(domain: str) -> str:
    return f"datasource.{domain}"


def get_override(domain: str) -> Optional[str]:
    """返回钉住的源名；auto/未设置/表缺失返回 None"""
    if domain not in DOMAINS:
        return None
    try:
        db = get_db()
        try:
            row = db.execute("SELECT value FROM settings WHERE key = ?", (_key(domain),)).fetchone()
        finally:
            db.close()
    except sqlite3.OperationalError:
        # settings 表缺失（测试临时库/极旧库）→ 视为 auto
        logger.debug("settings 表不可用，数据源配置视为 auto")
        return None
    value = row["value"] if row else "auto"
    return value if value != "auto" else None


def set_override(domain: str, source: str) -> None:
    """设置（auto 或合法源名）；非法值抛 ValueError"""
    if domain not in DOMAINS:
        raise ValueError(f"未知数据域: {domain}，可选 {DOMAINS}")
    if source != "auto" and source not in OPTIONS[domain]:
        raise ValueError(f"域 {domain} 不支持数据源 {source}，可选 auto/{'/'.join(OPTIONS[domain])}")
    db = get_db()
    try:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (_key(domain), source),
        )
        db.commit()
    finally:
        db.close()


def get_config() -> Dict[str, dict]:
    """全量配置：{domain: {mode, source, options: [{value, label}]}}"""
    out: Dict[str, dict] = {}
    for domain in DOMAINS:
        override = get_override(domain)
        out[domain] = {
            "mode": "fixed" if override else "auto",
            "source": override,
            "options": [{"value": v, "label": label_of(v)} for v in OPTIONS[domain]],
        }
    return out


def ordered_by_preference(chain: List, domain: str) -> List:
    """按用户配置重排链：钉住的源排首，其余保持原序；无配置原样返回"""
    override = get_override(domain)
    if not override:
        return chain
    name_map = {cls.name: cls for cls in chain}
    if override not in name_map:
        return chain
    return [name_map[override]] + [cls for cls in chain if cls.name != override]
