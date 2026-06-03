"""多因子库（v1.0 MVP 范围：10+ 因子）

五大类：
- 估值（Value）: PE / PB / PS / PEG
- 成长（Growth）: ROE / ROA / 营收增速 / 净利润增速
- 质量（Quality）: 毛利率 / 净利率 / 资产负债率 / 现金流
- 动量（Momentum）: N 日涨幅 / 量比
- 波动（Volatility）: ATR / 历史波动率 / Beta

数据源优先级：Tushare Pro（首选，A 股财务）→ AkShare（兜底）
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional


# ── 估值因子 ────────────────────────────────────────────────────

def factor_pe_ttm(pe: pd.Series) -> pd.Series:
    """PE-TTM（越小越便宜）"""
    return pe


def factor_pb(pb: pd.Series) -> pd.Series:
    """PB（市净率）"""
    return pb


def factor_ps_ttm(ps: pd.Series) -> pd.Series:
    """PS-TTM（市销率）"""
    return ps


# ── 成长因子 ────────────────────────────────────────────────────

def factor_roe(roe: pd.Series) -> pd.Series:
    """ROE（净资产收益率）"""
    return roe


def factor_roa(roa: pd.Series) -> pd.Series:
    """ROA（总资产收益率）"""
    return roa


def factor_revenue_yoy(growth: pd.Series) -> pd.Series:
    """营收同比增速"""
    return growth


def factor_profit_yoy(growth: pd.Series) -> pd.Series:
    """净利润同比增速"""
    return growth


# ── 质量因子 ────────────────────────────────────────────────────

def factor_gross_margin(gm: pd.Series) -> pd.Series:
    """毛利率"""
    return gm


def factor_net_margin(nm: pd.Series) -> pd.Series:
    """净利率"""
    return nm


def factor_debt_ratio(dr: pd.Series) -> pd.Series:
    """资产负债率（越小越稳健）"""
    return dr


# ── 动量因子 ────────────────────────────────────────────────────

def factor_momentum(close: pd.Series, period: int = 20) -> pd.Series:
    """N 日动量 = (close - close.shift(N)) / close.shift(N)"""
    return close.pct_change(periods=period)


def factor_turnover_rate(turn: pd.Series) -> pd.Series:
    """换手率"""
    return turn


# ── 波动因子 ────────────────────────────────────────────────────

def factor_atr_pct(atr: pd.Series, close: pd.Series) -> pd.Series:
    """ATR / close（波动率归一化）"""
    return atr / close.replace(0, np.nan)


def factor_hist_vol(close: pd.Series, period: int = 20) -> pd.Series:
    """历史波动率（年化）"""
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(period).std() * np.sqrt(252)


def factor_beta(stock_ret: pd.Series, bench_ret: pd.Series, period: int = 60) -> pd.Series:
    """Beta（相对基准）"""
    cov = stock_ret.rolling(period).cov(bench_ret)
    var = bench_ret.rolling(period).var()
    return cov / var.replace(0, np.nan)


# ── 因子注册表 ─────────────────────────────────────────────────

FACTOR_REGISTRY = {
    # 估值
    "pe_ttm":           {"fn": factor_pe_ttm,        "category": "估值", "direction": "desc"},  # 越小越好
    "pb":               {"fn": factor_pb,            "category": "估值", "direction": "desc"},
    "ps_ttm":           {"fn": factor_ps_ttm,        "category": "估值", "direction": "desc"},
    # 成长
    "roe":              {"fn": factor_roe,           "category": "成长", "direction": "asc"},
    "roa":              {"fn": factor_roa,           "category": "成长", "direction": "asc"},
    "revenue_yoy":      {"fn": factor_revenue_yoy,   "category": "成长", "direction": "asc"},
    "profit_yoy":       {"fn": factor_profit_yoy,    "category": "成长", "direction": "asc"},
    # 质量
    "gross_margin":     {"fn": factor_gross_margin,  "category": "质量", "direction": "asc"},
    "net_margin":       {"fn": factor_net_margin,    "category": "质量", "direction": "asc"},
    "debt_ratio":       {"fn": factor_debt_ratio,    "category": "质量", "direction": "desc"},
    # 动量
    "momentum_20d":     {"fn": lambda s: factor_momentum(s, 20), "category": "动量", "direction": "asc"},
    "momentum_60d":     {"fn": lambda s: factor_momentum(s, 60), "category": "动量", "direction": "asc"},
    "turnover_rate":    {"fn": factor_turnover_rate, "category": "动量", "direction": "asc"},
    # 波动
    "atr_pct":          {"fn": factor_atr_pct,       "category": "波动", "direction": "desc"},  # 低波动偏好
    "hist_vol_20d":     {"fn": factor_hist_vol,      "category": "波动", "direction": "desc"},
}


def list_factors() -> list[dict]:
    """列出所有因子（前端展示用）"""
    return [
        {
            "name": name,
            "category": meta["category"],
            "direction": meta["direction"],  # asc=越大越好, desc=越小越好
        }
        for name, meta in FACTOR_REGISTRY.items()
    ]


def cross_sectional_rank(df: pd.DataFrame, factor_col: str, ascending: bool = True) -> pd.Series:
    """截面分位排名（1 = 最高因子值）

    df 同一天有多个 ticker；按 factor_col 在当天横截面排序，给每个 ticker 赋 1..N 的排名。
    """
    return df.groupby("trade_date")[factor_col].rank(method="min", ascending=ascending)
