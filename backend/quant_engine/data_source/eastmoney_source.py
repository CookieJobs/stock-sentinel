"""东方财富数据源 — 复用 backend.data_fetcher 的 K 线逻辑

K 线 API: push2his.eastmoney.com/api/qt/stock/kline/get
- klt: 101=日K, 102=周K, 103=月K, 5/15/30/60=分钟K
- fqt: 1=前复权, 2=后复权, 0=不复权
"""
from __future__ import annotations
import time
import logging
from typing import Optional

import pandas as pd
import requests

from .base import DataSourceBase

logger = logging.getLogger(__name__)

EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://quote.eastmoney.com/",
}

# 周期映射：lightweight-charts/前端 → 东方财富
PERIOD_MAP = {
    "1d":  101,
    "1w":  102,
    "1mo": 103,
    "1m":  1,
    "5m":  5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
}


class EastMoneySource(DataSourceBase):
    name = "eastmoney"

    def get_kline(self, ticker: str, market: str, period: str = "1d",
                  start: Optional[str] = None, end: Optional[str] = None,
                  adj: str = "qfq") -> pd.DataFrame:
        secid = self._secid(ticker, market)
        klt = PERIOD_MAP.get(period, 101)
        fqt = {"qfq": 1, "hfq": 2, "none": 0}.get(adj, 1)

        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": klt,
            "fqt": fqt,
            "end": (end or "20500101").replace("-", ""),
            "lmt": 1000,  # 拉最多 1000 根
        }

        for attempt in range(3):
            try:
                resp = requests.get(EASTMONEY_KLINE_URL, params=params, headers=HEADERS, timeout=15)
                if resp.status_code == 200:
                    break
            except Exception:
                if attempt < 2:
                    time.sleep(0.3)
        else:
            return pd.DataFrame()

        data = resp.json().get("data")
        if not data or not data.get("klines"):
            return pd.DataFrame()

        rows = []
        for line in data["klines"]:
            parts = line.split(",")
            if len(parts) < 6:
                continue
            rows.append({
                "trade_date": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": float(parts[5]),
                "amount": float(parts[6]) if len(parts) > 6 else None,
            })
        df = pd.DataFrame(rows)
        if start:
            df = df[df["trade_date"] >= start]
        if end:
            df = df[df["trade_date"] <= end]
        return df.reset_index(drop=True)

    @staticmethod
    def _secid(ticker: str, market: str) -> str:
        clean = ticker.upper().replace(".HK", "")
        if market == "CN":
            if clean[0] in ("6", "9"):
                return f"1.{clean}"
            return f"0.{clean}"
        if market == "HK":
            return f"116.{clean.zfill(5)}"
        if market == "US":
            # 美股走 Finnhub，这里只是占位
            return f"105.{clean}"
        raise ValueError(f"Unsupported market: {market}")
