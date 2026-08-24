"""数据源抽象层

统一接口：get_kline(ticker, market, period, start, end, adj) → pd.DataFrame
- columns: trade_date, open, high, low, close, volume, amount
- 默认按 trade_date 升序

多市场支持：
- CN（A股）：AkShare（封装好）/ BaoStock（5+年日K + PE/PB）/ 东方财富（兜底 + 分钟K）
- HK（港股）：东方财富
- US（美股）：Finnhub（已有）
"""
from .eastmoney_source import EastMoneySource
from .akshare_source import AkShareSource
from .finnhub_source import FinnHubSource
from .baostock_source import BaoStockSource
from .ths_source import THSKlineSource
from .base import DataSourceBase


# 数据源优先级：同花顺（官方日线，需 key）→ AkShare → BaoStock → 东方财富（兜底 + 分钟K）
SOURCES = {
    "CN": [THSKlineSource, AkShareSource, BaoStockSource, EastMoneySource],
    "HK": [EastMoneySource, AkShareSource],
    "US": [FinnHubSource],
}


def get_kline(ticker: str, market: str, period: str = "1d",
              start: str = None, end: str = None, adj: str = "qfq") -> "pd.DataFrame":
    """统一 K 线获取入口

    按 SOURCES 优先级逐个尝试（用户可在 /settings 钉住某个源优先），失败则降级到下一个。
    """
    from datasource_config import ordered_by_preference
    sources = ordered_by_preference(SOURCES.get(market, []), "kline")
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
