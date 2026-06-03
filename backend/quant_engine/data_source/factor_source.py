"""因子数据源抽象 — 选股器数据接入

3 个 source：
- TushareSource: Tushare Pro（首选，A 股财务最全）
- AkShareSource: 东方财富/AkShare 实时全 A 股 spot（含 PE/PB/换手率/总市值等）
- MockSource: 模拟全 A 股（开发演示，Tushare + AkShare 不可用时使用）
"""
from __future__ import annotations
import os
import time
import random
import logging
from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class FactorSourceBase(ABC):
    """因子数据源基类"""

    name: str = "Base"

    @abstractmethod
    def get_universe(self) -> pd.DataFrame:
        """获取全 A 股列表 + 基础因子

        Returns DataFrame columns:
          ticker, name, market, industry, pe_ttm, pb, ps_ttm,
          market_cap, turnover_rate, change_pct, roe, gross_margin
        """
        raise NotImplementedError


class AkShareFactorSource(FactorSourceBase):
    """AkShare 实时全 A 股 spot"""

    name = "akshare"

    def get_universe(self) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError:
            return pd.DataFrame()
        try:
            df = ak.stock_zh_a_spot_em()
        except Exception as e:
            logger.warning("ak.stock_zh_a_spot_em failed: %s", e)
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()

        # 标准化列名（东方财富接口字段名）
        col_map = {
            "代码": "ticker",
            "名称": "name",
            "最新价": "price",
            "涨跌幅": "change_pct",
            "市盈率-动态": "pe_ttm",
            "市净率": "pb",
            "总市值": "market_cap",
            "流通市值": "float_cap",
            "换手率": "turnover_rate",
            "60日涨跌幅": "change_60d",
            "年初至今涨跌幅": "change_ytd",
        }
        df = df.rename(columns=col_map)
        # 选出我们需要的列
        keep = ["ticker", "name", "price", "change_pct", "pe_ttm", "pb",
                "market_cap", "float_cap", "turnover_rate", "change_60d", "change_ytd"]
        df = df[[c for c in keep if c in df.columns]].copy()
        df["market"] = "CN"
        df["industry"] = None  # 东方财富 spot 不含行业，行业用股票基本信息表
        return df.reset_index(drop=True)


class TushareFactorSource(FactorSourceBase):
    """Tushare Pro 财务数据（需 TUSHARE_TOKEN 环境变量）"""

    name = "tushare"

    def __init__(self):
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN not set")
        ts.set_token(token)
        self.pro = ts.pro_api()

    def get_universe(self) -> pd.DataFrame:
        # 拉全 A 股基础信息（含行业）
        df_basic = self.pro.stock_basic(list_status="L",
                                        fields="ts_code,name,industry,market,exchange,list_date")
        # 简化：ticker 用 ts_code 的数字部分
        df_basic["ticker"] = df_basic["ts_code"].str.split(".").str[0]
        df_basic["market"] = "CN"
        df_basic = df_basic.rename(columns={"industry": "industry"})

        # 拉最新一天的 daily_basic（含 PE/PB/换手率/市值等）
        today = pd.Timestamp.now().strftime("%Y%m%d")
        df_daily = self.pro.daily_basic(trade_date=today)
        if df_daily is None or df_daily.empty:
            # fallback 到最近一个有数据的日期
            df_cal = self.pro.trade_cal(exchange="SSE", is_open="1",
                                        start_date=(pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y%m%d"),
                                        end_date=today)
            if df_cal is not None and not df_cal.empty:
                last_date = df_cal["cal_date"].iloc[-1]
                df_daily = self.pro.daily_basic(trade_date=last_date)

        if df_daily is None or df_daily.empty:
            return df_basic

        df_daily["ticker"] = df_daily["ts_code"].str.split(".").str[0]
        rename = {
            "pe_ttm": "pe_ttm", "pb": "pb", "ps_ttm": "ps_ttm",
            "total_mv": "market_cap", "circ_mv": "float_cap",
            "turnover_rate": "turnover_rate", "pct_chg": "change_pct",
        }
        df_daily = df_daily.rename(columns=rename)
        # 合并
        df = df_basic.merge(df_daily, on="ticker", how="left", suffixes=("", "_dup"))
        keep = ["ticker", "name", "industry", "market", "pe_ttm", "pb", "ps_ttm",
                "market_cap", "float_cap", "turnover_rate", "change_pct"]
        return df[[c for c in keep if c in df.columns]].reset_index(drop=True)


class MockFactorSource(FactorSourceBase):
    """Mock 全 A 股列表（开发演示，Tushare + AkShare 不可用时使用）

    生成 ~5000 只"看似真实"的股票数据，含 ticker / name / industry / PE / PB / 换手率 / 市值 / 涨跌
    行业分布与现实 A 股大致一致
    """

    name = "mock"
    INDUSTRIES = [
        "银行", "白酒", "地产", "汽车", "医药", "半导体", "互联网", "保险",
        "电力", "煤炭", "石油", "钢铁", "有色金属", "化工", "建材",
        "家电", "食品饮料", "纺织服饰", "传媒", "通信", "计算机", "电子",
        "机械设备", "国防军工", "农林牧渔", "环保", "物流", "零售",
    ]
    # ticker 段位和真实股票大致匹配
    SH_PREFIXES = ["600", "601", "603", "605"]
    SZ_PREFIXES = ["000", "001", "002", "003", "300", "301"]

    def get_universe(self) -> pd.DataFrame:
        random.seed(42)
        rows = []
        # 沪市 ~2000 只
        for prefix in self.SH_PREFIXES:
            for _ in range(500):
                ticker = f"{prefix}{random.randint(100, 999)}"
                rows.append(self._gen_row(ticker, "SH"))
        # 深市 ~3000 只
        for prefix in self.SZ_PREFIXES:
            for _ in range(500):
                ticker = f"{prefix}{random.randint(100, 999)}"
                rows.append(self._gen_row(ticker, "SZ"))
        df = pd.DataFrame(rows)
        # 去重
        df = df.drop_duplicates(subset=["ticker"]).reset_index(drop=True)
        return df

    def _gen_row(self, ticker: str, exchange: str) -> dict:
        # 真实分布：银行 PE 低、半导体 PE 高、白酒 30+
        industry = random.choice(self.INDUSTRIES)
        if industry == "银行":
            pe = random.uniform(4, 8)
            pb = random.uniform(0.5, 1.2)
            roe = random.uniform(0.08, 0.15)
        elif industry == "白酒":
            pe = random.uniform(15, 40)
            pb = random.uniform(3, 8)
            roe = random.uniform(0.15, 0.30)
        elif industry == "半导体":
            pe = random.uniform(40, 200)
            pb = random.uniform(3, 15)
            roe = random.uniform(0.05, 0.20)
        elif industry == "互联网":
            pe = random.uniform(15, 60)
            pb = random.uniform(2, 8)
            roe = random.uniform(0.10, 0.25)
        elif industry == "地产":
            pe = random.uniform(3, 30)
            pb = random.uniform(0.3, 2.0)
            roe = random.uniform(0.0, 0.15)
        else:
            pe = random.uniform(10, 80)
            pb = random.uniform(1, 6)
            roe = random.uniform(0.03, 0.20)

        market_cap = random.uniform(20, 5000)  # 亿
        return {
            "ticker": ticker,
            "name": f"{industry}股票{ticker[-3:]}",
            "industry": industry,
            "market": "CN",
            "exchange": exchange,
            "price": round(random.uniform(2, 300), 2),
            "change_pct": round(random.gauss(0, 3), 2),
            "pe_ttm": round(pe, 2),
            "pb": round(pb, 2),
            "ps_ttm": round(random.uniform(1, 10), 2),
            "market_cap": round(market_cap, 2),
            "float_cap": round(market_cap * random.uniform(0.3, 0.95), 2),
            "turnover_rate": round(random.uniform(0.1, 8.0), 2),
            "change_60d": round(random.gauss(0, 20), 2),
            "change_ytd": round(random.gauss(5, 30), 2),
            "roe": round(roe, 4),
            "gross_margin": round(random.uniform(0.1, 0.6), 4),
        }


# 数据源优先级：Tushare > AkShare > Mock
SOURCES = [TushareFactorSource, AkShareFactorSource, MockFactorSource]


def get_factor_source():
    """按优先级选择第一个可用的数据源"""
    for src_cls in SOURCES:
        try:
            if src_cls is TushareFactorSource and not os.environ.get("TUSHARE_TOKEN"):
                continue
            src = src_cls()
            logger.info("Using factor source: %s", src.name)
            return src
        except Exception as e:
            logger.debug("Source %s not available: %s", src_cls.__name__, e)
            continue
    # 兜底返回 mock
    return MockFactorSource()
