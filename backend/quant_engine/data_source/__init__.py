"""数据源抽象层

统一接口：get_kline(ticker, market, period, start, end, adj) → pd.DataFrame
- columns: trade_date, open, high, low, close, volume, amount
- 默认按 trade_date 升序

多市场支持：
- CN（A股）：东方财富（已有，main.py/data_fetcher.py 用的就是）/ AkShare（兜底）
- HK（港股）：东方财富
- US（美股）：Finnhub（已有）
"""
from .eastmoney_source import EastMoneySource
from .akshare_source import AkShareSource
from .finnhub_source import FinnHubSource
from .base import DataSourceBase


# 数据源优先级：akshare 优先（封装好）→ 东方财富（直接）→ Finnhub（美股）
SOURCES = {
    "CN": [AkShareSource, EastMoneySource],
    "HK": [EastMoneySource, AkShareSource],
    "US": [FinnHubSource],
}


def get_kline(ticker: str, market: str, period: str = "1d",
              start: str = None, end: str = None, adj: str = "qfq") -> "pd.DataFrame":
    """统一 K 线获取入口

    按 SOURCES 优先级逐个尝试，失败则降级到下一个。
    """
    sources = SOURCES.get(market, [])
    last_err = None
    for source_cls in sources:
        try:
            source = source_cls()
            df = source.get_kline(ticker, market, period, start, end, adj)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"All data sources failed for {ticker}/{market}: {last_err}")
