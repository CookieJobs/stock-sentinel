"""AkShare 数据源 — A 股免费开源数据

AkShare 优势：开源、社区活跃、A 股数据最全（财务/资金流/龙虎榜）
- 日 K: ak.stock_zh_a_hist(symbol, period, start, end, adjust)
- 财务: ak.stock_financial_report_sina / ak.stock_zh_a_indicator
- 实时: ak.stock_zh_a_spot_em()
"""
from __future__ import annotations
from typing import Optional

import pandas as pd

from .base import DataSourceBase


# AkShare period: daily/weekly/monthly
PERIOD_MAP = {
    "1d":  "daily",
    "1w":  "weekly",
    "1mo": "monthly",
}


class AkShareSource(DataSourceBase):
    name = "akshare"

    def get_kline(self, ticker: str, market: str, period: str = "1d",
                  start: Optional[str] = None, end: Optional[str] = None,
                  adj: str = "qfq") -> pd.DataFrame:
        if market != "CN":
            return pd.DataFrame()
        try:
            import akshare as ak
        except ImportError:
            return pd.DataFrame()

        ak_period = PERIOD_MAP.get(period, "daily")
        ak_adj = {"qfq": "qfq", "hfq": "hfq", "none": ""}.get(adj, "qfq")
        # AkShare 需要 6 位纯数字 ticker
        clean = ticker.upper().replace(".HK", "")
        if not clean.isdigit() or len(clean) != 6:
            return pd.DataFrame()

        try:
            df = ak.stock_zh_a_hist(
                symbol=clean,
                period=ak_period,
                start_date=(start or "20200101").replace("-", ""),
                end_date=(end or "20500101").replace("-", ""),
                adjust=ak_adj,
            )
        except Exception:
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        # 标准化列名
        rename = {
            "日期": "trade_date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
        df = df.rename(columns=rename)
        keep = ["trade_date", "open", "close", "high", "low", "volume", "amount"]
        df = df[[c for c in keep if c in df.columns]]
        # trade_date 格式化
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
        return df.reset_index(drop=True)
