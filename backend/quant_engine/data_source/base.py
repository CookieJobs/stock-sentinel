"""数据源基类"""
from __future__ import annotations
import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional


class DataSourceBase(ABC):
    """统一数据源接口"""

    name: str = "Base"

    @abstractmethod
    def get_kline(self, ticker: str, market: str, period: str = "1d",
                  start: Optional[str] = None, end: Optional[str] = None,
                  adj: str = "qfq") -> pd.DataFrame:
        """获取 K 线

        Returns: DataFrame with columns [trade_date, open, high, low, close, volume, amount]
        """
        raise NotImplementedError
