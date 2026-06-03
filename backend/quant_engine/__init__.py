"""StockSentinel 量化分析引擎（quant_engine）

v1.0 MVP 范围（1-2 月）：
- Tier 1 全部：K线 + 图表 + 15+ 指标 + 历史数据 + 10+ 因子 + 回测 + 组合 + 风险 + 基准

模块划分：
- indicators : 技术指标（MA/EMA/MACD/RSI/BOLL/KDJ/ATR/OBV/CCI/WR/BBI/SAR/成交量等）
- factors    : 多因子（估值/成长/质量/动量/波动）
- backtest   : 事件驱动回测引擎
- portfolio  : 组合管理（多股 + 权重 + 再平衡）
- risk       : 风险指标（夏普/最大回撤/波动率/Beta/Alpha）+ 基准对比
- data_source: 数据源封装（akshare / tushare / finnhub / 东方财富）
- api        : FastAPI 路由
- db         : 量化相关表（kline / daily_metrics / factor_values / portfolios / backtests）

设计原则：
- 参考 QuantConnect Lean 思想，事件驱动
- 不引第三方回测库（自研，灵活）
- 优先用免费数据源：东方财富 + AkShare + Tushare 积分档 + Finnhub 免费档
"""
__version__ = "0.1.0"
