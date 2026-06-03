"""技术指标库（v1.0 MVP 范围：15+ 指标）

所有指标接收 pd.Series 输入（close / high / low / volume），返回 pd.Series 输出。
不做前向看（避免未来数据泄露），naive 实现优先；后续可加 numba 加速。

指标清单：
- 趋势：MA, EMA, MACD, BBI, SAR
- 震荡：RSI, KDJ, CCI, WR
- 波动：BOLL, ATR
- 成交量：OBV, VOL_MA

设计原则：
- 纯函数：pd.Series → pd.Series，无副作用
- 参数化：周期/阈值都可调
- 易测：单测覆盖每个指标的 happy path
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional


# ── 趋势类 ──────────────────────────────────────────────────────

def MA(close: pd.Series, period: int = 5) -> pd.Series:
    """简单移动平均线"""
    return close.rolling(period, min_periods=1).mean()


def EMA(close: pd.Series, period: int = 12) -> pd.Series:
    """指数移动平均线"""
    return close.ewm(span=period, adjust=False).mean()


def MACD(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """MACD 指标（返回 dif / dea / bar 三个 Series）"""
    ema_fast = EMA(close, fast)
    ema_slow = EMA(close, slow)
    dif = ema_fast - ema_slow
    dea = EMA(dif, signal)
    bar = (dif - dea) * 2
    return {"dif": dif, "dea": dea, "bar": bar}


def BBI(close: pd.Series) -> pd.Series:
    """多空指数（BBI = (MA3 + MA6 + MA12 + MA24) / 4）"""
    return (MA(close, 3) + MA(close, 6) + MA(close, 12) + MA(close, 24)) / 4


def SAR(high: pd.Series, low: pd.Series, step: float = 0.02, max_step: float = 0.2) -> pd.Series:
    """抛物线 SAR（Wilder 完整算法）

    上升趋势：SAR 位于价格下方，作支撑
    下降趋势：SAR 位于价格上方，作压力
    反转：SAR 穿越价格 → 趋势翻转
    """
    n = len(high)
    if n < 2:
        return pd.Series([np.nan] * n, index=high.index)

    h = high.values
    l = low.values
    sar = np.full(n, np.nan)

    is_long = True           # 假设起始为上升
    af = step                 # 加速因子
    ep = h[0]                 # 极值点
    sar[0] = l[0]

    for i in range(1, n):
        prev_sar = sar[i-1]
        if np.isnan(prev_sar):
            sar[i] = l[i] if is_long else h[i]
            continue

        if is_long:
            sar[i] = prev_sar + af * (ep - prev_sar)
            # 反转：价格跌破 SAR
            if l[i] < sar[i]:
                is_long = False
                sar[i] = ep          # 反转时 SAR 设到极值
                ep = l[i]
                af = step
            else:
                if h[i] > ep:
                    ep = h[i]
                    af = min(af + step, max_step)
        else:
            sar[i] = prev_sar + af * (ep - prev_sar)
            # 反转：价格涨破 SAR
            if h[i] > sar[i]:
                is_long = True
                sar[i] = ep
                ep = h[i]
                af = step
            else:
                if l[i] < ep:
                    ep = l[i]
                    af = min(af + step, max_step)

    return pd.Series(sar, index=high.index)


# ── 震荡类 ──────────────────────────────────────────────────────

def RSI(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI（相对强弱指标）

    边界处理：
    - 无下跌（avg_loss=0）→ RSI = 100（强势）
    - 无上涨（avg_gain=0）→ RSI = 0（弱势）
    - 都不为 0 → 正常公式 100 - 100/(1+RS)
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    raw = 100 - 100 / (1 + rs)
    # 修复：avg_loss=0 → RSI=100（无下跌），avg_gain=0 → RSI=0（无上涨）
    return raw.where(avg_loss > 0, 100.0).where(avg_gain > 0, 0.0)


def KDJ(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9, m1: int = 3, m2: int = 3) -> dict:
    """KDJ 随机指标（返回 K / D / J 三个 Series）"""
    low_n = low.rolling(n, min_periods=1).min()
    high_n = high.rolling(n, min_periods=1).max()
    rsv = (close - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    rsv = rsv.fillna(50.0)
    k = rsv.ewm(alpha=1/m1, adjust=False).mean()
    d = k.ewm(alpha=1/m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return {"k": k, "d": d, "j": j}


def CCI(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """CCI 顺势指标"""
    tp = (high + low + close) / 3
    ma = tp.rolling(period, min_periods=1).mean()
    md = tp.rolling(period, min_periods=1).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - ma) / (0.015 * md).replace(0, np.nan)


def WR(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """威廉指标 (Williams %R)"""
    high_n = high.rolling(period, min_periods=1).max()
    low_n = low.rolling(period, min_periods=1).min()
    return (high_n - close) / (high_n - low_n).replace(0, np.nan) * -100


# ── 波动类 ──────────────────────────────────────────────────────

def BOLL(close: pd.Series, period: int = 20, stddev: float = 2.0) -> dict:
    """布林带（返回 mid / upper / lower 三个 Series）"""
    mid = MA(close, period)
    std = close.rolling(period, min_periods=1).std()
    return {"mid": mid, "upper": mid + stddev * std, "lower": mid - stddev * std}


def ATR(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """平均真实波幅"""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


# ── 成交量类 ────────────────────────────────────────────────────

def OBV(close: pd.Series, volume: pd.Series) -> pd.Series:
    """能量潮"""
    sign = np.sign(close.diff()).fillna(0)
    return (sign * volume).cumsum()


def VOL_MA(volume: pd.Series, period: int = 5) -> pd.Series:
    """成交量均线"""
    return volume.rolling(period, min_periods=1).mean()


# ── 入口：批量计算 ─────────────────────────────────────────────

INDICATORS = {
    "MA":   {"fn": MA,   "params": {"period": 5},   "inputs": ["close"]},
    "EMA":  {"fn": EMA,  "params": {"period": 12},  "inputs": ["close"]},
    "MACD": {"fn": MACD, "params": {"fast": 12, "slow": 26, "signal": 9}, "inputs": ["close"], "multi": True},
    "BBI":  {"fn": BBI,  "params": {},              "inputs": ["close"]},
    "RSI":  {"fn": RSI,  "params": {"period": 14},  "inputs": ["close"]},
    "KDJ":  {"fn": KDJ,  "params": {"n": 9, "m1": 3, "m2": 3}, "inputs": ["high", "low", "close"], "multi": True},
    "CCI":  {"fn": CCI,  "params": {"period": 14},  "inputs": ["high", "low", "close"]},
    "WR":   {"fn": WR,   "params": {"period": 14},  "inputs": ["high", "low", "close"]},
    "BOLL": {"fn": BOLL, "params": {"period": 20, "stddev": 2.0}, "inputs": ["close"], "multi": True},
    "ATR":  {"fn": ATR,  "params": {"period": 14},  "inputs": ["high", "low", "close"]},
    "OBV":  {"fn": OBV,  "params": {},              "inputs": ["close", "volume"]},
    "VOL_MA": {"fn": VOL_MA, "params": {"period": 5}, "inputs": ["volume"]},
    "SAR":   {"fn": SAR,   "params": {"step": 0.02, "max_step": 0.2}, "inputs": ["high", "low"]},
}


# 振荡器（在主图下方独立 pane 显示的指标）
OSCILLATOR_INDICATORS = {"MACD", "RSI", "KDJ", "WR", "CCI", "ATR"}


def list_indicators() -> list[dict]:
    """列出所有可用指标（前端展示用）"""
    return [
        {
            "name": name,
            "params": meta["params"],
            "multi": meta.get("multi", False),
            "oscillator": name in OSCILLATOR_INDICATORS,
        }
        for name, meta in INDICATORS.items()
    ]


def compute(name: str, df: pd.DataFrame, **override_params) -> dict:
    """根据指标名和数据计算，返回 {series_name: pd.Series, ...}

    df 必须包含 close / high / low / volume 至少之一。
    """
    if name not in INDICATORS:
        raise ValueError(f"Unknown indicator: {name}. Available: {list(INDICATORS)}")
    meta = INDICATORS[name]
    params = {**meta["params"], **override_params}
    inputs = {col: df[col] for col in meta["inputs"]}
    return meta["fn"](**inputs, **params)
