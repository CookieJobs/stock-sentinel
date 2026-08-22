"""东财延时行情因子源 — push2delay clist 全 A 股（15 分钟延时，无配额限制）

调研结论（2026-08-20）：`push2delay.eastmoney.com` 与 `push2` 同一套 API 形状，
但**不触发 push2 的服务端风控**（本机实测稳定 200，total=5552），可提供全市场
PE/PB/换手率/市值/行业/ROE，完全替代 Tushare `daily_basic` 的角色（日频因子
不介意 15 分钟延时）。

clist 字段映射（EastMoney）：
  f2 最新价 / f3 涨跌幅 / f8 换手率 / f9 市盈率(动) / f12 代码 / f14 名称
  f20 总市值(元) / f21 流通市值(元) / f23 市净率 / f37 净资产收益率ROE(%)
  f100 行业 / f115 市盈率TTM / f116 市销率TTM（如返回）
"""
import logging
import time
from typing import Optional

import pandas as pd
import requests

from .base import FactorSourceBase

logger = logging.getLogger(__name__)

CLIST_URL = "https://push2delay.eastmoney.com/api/qt/clist/get"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
# 沪深 A 股：深主板+创业板+沪主板+科创板
FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
FIELDS = "f2,f3,f8,f9,f12,f14,f20,f21,f23,f37,f100,f115,f116"
PAGE_SIZE = 100   # API 实际单页上限（实测 pz=200 也只返回 100）
MAX_PAGES = 60    # 防御：5552 只 / 100 ≈ 56 页
RETRIES = 3       # 每页失败重试次数（后段页实测偶发超时）

_FIELD_MAP = {
    "f12": "ticker", "f14": "name", "f100": "industry",
    "f3": "change_pct", "f8": "turnover_rate",
    "f9": "pe_dyn", "f115": "pe_ttm", "f116": "ps_ttm", "f23": "pb",
    "f20": "market_cap", "f21": "float_cap", "f37": "roe",
}

_NUM_COLS = ("change_pct", "turnover_rate", "pe_dyn", "pe_ttm", "ps_ttm",
             "pb", "market_cap", "float_cap", "roe")


class EastMoneyDelayFactorSource(FactorSourceBase):
    """东财延时行情全 A 股因子源（无 key、无配额）"""

    name = "eastmoney_delay"

    def get_universe(self) -> pd.DataFrame:
        rows = []
        total = None
        for page in range(1, MAX_PAGES + 1):
            diff = []
            for attempt in range(RETRIES):
                try:
                    resp = requests.get(
                        CLIST_URL,
                        params={
                            "pn": page, "pz": PAGE_SIZE, "po": 1, "np": 1,
                            "fltt": 2, "invt": 2, "fid": "f3",
                            "fs": FS, "fields": FIELDS,
                        },
                        timeout=15,
                        headers=HEADERS,
                    )
                    if resp.status_code != 200:
                        raise RuntimeError(f"HTTP {resp.status_code}")
                    data = resp.json().get("data") or {}
                    if total is None:
                        total = int(data.get("total") or 0)
                    diff = data.get("diff") or []
                    break
                except Exception as e:
                    logger.warning("clist page %d attempt %d/%d failed: %s",
                                   page, attempt + 1, RETRIES, e)
                    time.sleep(1)
            if not diff:
                logger.warning("clist page %d empty after %d retries, stop", page, RETRIES)
                break
            rows.extend(diff)
            if total and len(rows) >= total:
                break
            if len(diff) < PAGE_SIZE:
                break

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df = df.rename(columns={k: v for k, v in _FIELD_MAP.items() if k in df.columns})
        df["ticker"] = df["ticker"].astype(str).str.zfill(6)
        df["market"] = "CN"
        # 数值化：缺失 / '-' → NaN
        for col in _NUM_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # PE-TTM 缺失时用动态 PE 兜底
        if "pe_ttm" not in df.columns and "pe_dyn" in df.columns:
            df["pe_ttm"] = df["pe_dyn"]
        elif "pe_ttm" in df.columns:
            df["pe_ttm"] = df["pe_ttm"].fillna(df.get("pe_dyn"))
        # 市值单位：东财为元，对齐 Tushare daily_basic 的万元
        for col in ("market_cap", "float_cap"):
            if col in df.columns:
                df[col] = df[col] / 1e4

        keep = ["ticker", "name", "industry", "market", "pe_ttm", "pb", "ps_ttm",
                "market_cap", "float_cap", "turnover_rate", "change_pct", "roe"]
        df = df[[c for c in keep if c in df.columns]].reset_index(drop=True)
        logger.info("EastMoneyDelay universe: %d rows (total=%s)", len(df), total)
        return df
