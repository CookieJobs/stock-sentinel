"""BaoStock 数据源 — A 股免费开源数据

BaoStock 优势：
- 无 token / 无积分 / 无频率限制（正常使用）
- 5+ 年 K 线数据
- K 线**自带** PE/PB/换手率字段（query_history_k_data_plus）
- 完整行业分类（query_stock_industry，申万行业）
- 完整财务数据（query_profit_data / query_growth_data / 等）

限制：
- A 股 + 指数（**无港股 / 美股**）
- 只支持 **日/周/月** K 线（**无分钟级**）
- session-based：单进程单 login，调用频率高了会触发服务端限流
- 行业 / 财务数据按 ticker 逐个 query，全 A 股约 5500 ticker × 数秒/个

策略：
- K-line：失败 → AkShare 兜底（不阻塞，重要）
- Factor (universe)：失败 → 不影响其他 source，链式 fallback 自然走 Tushare / AkShare / Mock
"""
from __future__ import annotations
import logging
import threading
from typing import Optional

import pandas as pd

from .base import DataSourceBase, FactorSourceBase

logger = logging.getLogger(__name__)


# ── BaoStock 周期映射（BaoStock 只支持 d/w/m） ──────────────────
PERIOD_MAP = {
    "1d":  "d",
    "1w":  "w",
    "1mo": "m",
}

# BaoStock 复权标志：1=后复权, 2=前复权, 3=不复权
ADJ_MAP = {
    "hfq": "1",
    "qfq": "2",
    "none": "3",
}


# ── 单例 session 管理（线程安全懒登录） ─────────────────────────

class _BaoStockSession:
    """单进程共享 BaoStock session

    BaoStock 一次 login 即可在该进程内反复使用，logout 释放。
    用双重检查锁保证多线程安全。
    """
    _instance = None
    _state_lock = threading.Lock()
    _logged_in = False

    @classmethod
    def get_bs(cls):
        """拿到 baostock 模块句柄（已登录）"""
        if not cls._logged_in:
            with cls._state_lock:
                if not cls._logged_in:
                    import baostock as bs
                    lg = bs.login()
                    if lg.error_code != "0":
                        raise RuntimeError(f"BaoStock login failed: {lg.error_msg}")
                    cls._logged_in = True
                    logger.info("BaoStock logged in")
        import baostock as bs
        return bs

    @classmethod
    def logout(cls):
        """进程退出时调用（可选，os 退出时 BaoStock 自动断开）"""
        with cls._state_lock:
            if cls._logged_in:
                try:
                    import baostock as bs
                    bs.logout()
                except Exception:
                    pass
                cls._logged_in = False
                logger.info("BaoStock logged out")


# ── K-line 数据源 ───────────────────────────────────────────────

class BaoStockSource(DataSourceBase):
    """BaoStock K-line 数据源（CN only，日/周/月）"""

    name = "baostock"

    def get_kline(self, ticker: str, market: str, period: str = "1d",
                  start: Optional[str] = None, end: Optional[str] = None,
                  adj: str = "qfq") -> pd.DataFrame:
        if market != "CN":
            return pd.DataFrame()
        if period not in PERIOD_MAP:
            # BaoStock 不支持分钟级
            return pd.DataFrame()

        bs_code = self._to_bs_code(ticker, market)
        if not bs_code:
            return pd.DataFrame()

        frequency = PERIOD_MAP[period]
        adj_flag = ADJ_MAP.get(adj, "2")
        start_date = (start or "20200101").replace("-", "")
        end_date = (end or "20500101").replace("-", "")

        try:
            bs = _BaoStockSession.get_bs()
        except Exception as e:
            logger.warning("BaoStock session init failed: %s", e)
            return pd.DataFrame()

        # K 线字段：含 PE/PB/换手率，但 v1 主要用 OHLCV，PE/PB 在 factor 层处理
        fields = "date,code,open,high,low,close,volume,amount"

        try:
            rs = bs.query_history_k_data_plus(
                code=bs_code,
                fields=fields,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag=adj_flag,
            )
        except Exception as e:
            logger.warning("BaoStock query_history_k_data_plus failed for %s: %s", bs_code, e)
            return pd.DataFrame()

        # BaoStock 在网络限流 / 错误时可能返回 None
        if rs is None:
            logger.warning("BaoStock returned None for %s (rate limit or network issue)", bs_code)
            return pd.DataFrame()

        if rs.error_code != "0":
            logger.warning("BaoStock error %s for %s: %s", rs.error_code, bs_code, rs.error_msg)
            return pd.DataFrame()

        data = rs.get_data()
        if data is None or data.empty:
            return pd.DataFrame()

        # BaoStock 列名：date/code/open/high/low/close/volume/amount
        rename = {
            "date": "trade_date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "amount": "amount",
        }
        data = data.rename(columns=rename)
        # 数值列：空字符串 / "-" → NaN
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")
        # 保留规范列
        keep = ["trade_date", "open", "high", "low", "close", "volume", "amount"]
        data = data[[c for c in keep if c in data.columns]]
        return data.reset_index(drop=True)

    @staticmethod
    def _to_bs_code(ticker: str, market: str) -> Optional[str]:
        """sh.600519 / sz.000001 格式

        支持的输入格式（不区分大小写）：
        - 600519            → sh.600519（按 6 开头推断）
        - SH.600519         → sh.600519（前缀清洗）
        - 600519.SH         → sh.600519（后缀清洗）
        - 0700.HK           → None（港股不在 BaoStock 范围）
        - 4/8/92 开头        → bj.830799（北交所）
        """
        import re
        t = ticker.strip()
        # 去掉前缀 xx.（如 sh.600519）→ 600519
        t = re.sub(r"^(sh|sz|bj|hk)\.", "", t, flags=re.IGNORECASE)
        # 去掉后缀 .xx（如 600519.SH）→ 600519
        t = re.sub(r"\.(sh|sz|bj|hk)$", "", t, flags=re.IGNORECASE)
        if not t.isdigit() or len(t) != 6:
            return None
        if t.startswith(("60", "601", "603", "605", "688", "9", "5")):
            return f"sh.{t}"
        if t.startswith(("00", "30", "002", "003", "301")):
            return f"sz.{t}"
        if t.startswith(("8", "4", "92")):
            return f"bj.{t}"
        # 兜底：根据 market 猜
        if market == "CN":
            return f"sh.{t}"
        return None


# ── Factor / Universe 数据源 ────────────────────────────────────

class BaoStockFactorSource(FactorSourceBase):
    """BaoStock 全 A 股 universe（含真实行业 + 名称）

    关键升级：相比 AkShareFactorSource，本源提供**申万行业分类**，
    能直接解掉 factor_service 的 industry 筛选 TODO。

    数据流：
    1. query_all_stock         → 全 A 股代码 + 名称 + 上市日期
    2. query_stock_industry    → 行业分类（申万）
    3. 合并后输出标准 universe schema

    估值字段（PE/PB/换手率/市值）：**暂不批量拉**——
    全 A 股逐 ticker query 太慢，v1 保持 None，由 daily_metrics 走 K-line 流后填。
    """
    name = "baostock"

    def get_universe(self) -> pd.DataFrame:
        try:
            bs = _BaoStockSession.get_bs()
        except Exception as e:
            logger.warning("BaoStock session init failed in factor source: %s", e)
            return pd.DataFrame()

        # Step 1: 全 A 股基础信息
        try:
            rs_basic = bs.query_all_stock(day=pd.Timestamp.now().strftime("%Y-%m-%d"))
            if rs_basic is None or rs_basic.error_code != "0":
                logger.warning("BaoStock query_all_stock error: %s",
                               rs_basic.error_msg if rs_basic else "None")
                return pd.DataFrame()
            df_basic = rs_basic.get_data()
            if df_basic is None or df_basic.empty:
                return pd.DataFrame()
        except Exception as e:
            logger.warning("BaoStock query_all_stock exception: %s", e)
            return pd.DataFrame()

        # BaoStock 列：code, code_name, ipoDate, outDate, type, status
        # code 格式: sh.600519 → 拆出 ticker + exchange
        df_basic["ticker"] = df_basic["code"].str.split(".").str[1]
        df_basic["exchange"] = df_basic["code"].str.split(".").str[0].str.upper()
        df_basic = df_basic.rename(columns={"code_name": "name"})
        df_basic["market"] = "CN"
        # 只保留交易中（status=1）
        if "status" in df_basic.columns:
            df_basic = df_basic[df_basic["status"] == "1"]
        logger.info("BaoStock basic: %d active A-share tickers", len(df_basic))

        # Step 2: 行业分类
        try:
            rs_ind = bs.query_stock_industry()
            if rs_ind is not None and rs_ind.error_code == "0":
                df_ind = rs_ind.get_data()
                if df_ind is not None and not df_ind.empty:
                    # BaoStock 行业列: code, code_name, industry, industryClassification
                    df_ind["ticker"] = df_ind["code"].str.split(".").str[1]
                    # 行业有 industry（中文名）和 industryClassification（编码）
                    # 用 industry（中文）作为 industry 字段
                    df_ind_use = df_ind[["ticker", "industry"]].drop_duplicates(subset=["ticker"])
                    df_basic = df_basic.merge(df_ind_use, on="ticker", how="left")
                    logger.info(
                        "BaoStock industry: %d tickers have industry, %d missing",
                        df_basic["industry"].notna().sum(),
                        df_basic["industry"].isna().sum(),
                    )
                else:
                    df_basic["industry"] = None
            else:
                logger.warning("BaoStock query_stock_industry error: %s", rs_ind.error_msg)
                df_basic["industry"] = None
        except Exception as e:
            logger.warning("BaoStock query_stock_industry exception: %s", e)
            df_basic["industry"] = None

        # 初始化缺失列（保持 schema 兼容）
        for col in ["pe_ttm", "pb", "ps_ttm", "market_cap", "float_cap",
                    "turnover_rate", "change_pct", "change_60d", "change_ytd",
                    "roe", "gross_margin"]:
            if col not in df_basic.columns:
                df_basic[col] = None

        # 标准列
        keep = ["ticker", "name", "market", "industry", "exchange",
                "pe_ttm", "pb", "ps_ttm",
                "market_cap", "float_cap",
                "turnover_rate", "change_pct", "change_60d", "change_ytd",
                "roe", "gross_margin"]
        return df_basic[[c for c in keep if c in df_basic.columns]].reset_index(drop=True)


# ── 测试 hook ───────────────────────────────────────────────────

def _reset_session_for_test():
    """测试用：重置 session 状态让 login 重跑（mock 用）"""
    _BaoStockSession._logged_in = False
    _BaoStockSession._instance = None
