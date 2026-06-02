"""FinnHub 数据源 — 美股

API 文档: https://finnhub.io/docs/api
- /stock/candle: K 线 (免费档有限制)
"""
from __future__ import annotations
import os
import time
from typing import Optional

import pandas as pd
import requests

from .base import DataSourceBase

FINNHUB_CANDLE_URL = "https://finnhub.io/api/v1/stock/candle"

# resolution: 1, 5, 15, 30, 60, D, W, M
RESOLUTION_MAP = {
    "1m":  1,
    "5m":  5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
    "1d":  "D",
    "1w":  "W",
    "1mo": "M",
}


class FinnHubSource(DataSourceBase):
    name = "finnhub"

    def __init__(self):
        self.api_key = os.environ.get("FINNHUB_API_KEY", "")

    def get_kline(self, ticker: str, market: str, period: str = "1d",
                  start: Optional[str] = None, end: Optional[str] = None,
                  adj: str = "qfq") -> pd.DataFrame:
        if market != "US" or not self.api_key:
            return pd.DataFrame()
        resolution = RESOLUTION_MAP.get(period, "D")
        # Finnhub 用 unix 时间戳
        from_ts = int(time.mktime(time.strptime(start, "%Y-%m-%d"))) if start else int(time.time()) - 365*24*3600
        to_ts = int(time.mktime(time.strptime(end, "%Y-%m-%d"))) if end else int(time.time())

        try:
            resp = requests.get(
                FINNHUB_CANDLE_URL,
                params={
                    "symbol": ticker.upper(),
                    "resolution": resolution,
                    "from": from_ts,
                    "to": to_ts,
                    "token": self.api_key,
                },
                timeout=15,
            )
        except Exception:
            return pd.DataFrame()

        if resp.status_code != 200:
            return pd.DataFrame()
        data = resp.json()
        if data.get("s") != "ok":
            return pd.DataFrame()

        df = pd.DataFrame({
            "trade_date": pd.to_datetime(data["t"], unit="s").strftime("%Y-%m-%d"),
            "open":  data["o"],
            "high":  data["h"],
            "low":   data["l"],
            "close": data["c"],
            "volume": data["v"],
        })
        return df
