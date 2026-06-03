# StockSentinel → 量化分析平台：路线图

> 文档目的：把当前 v0.2.0 的「监控+告警」工具，分阶段升级为对标世界领先水平的个人投研型量化分析平台。
> 
> **v1 决策（2026-06-02 拍板）**：
> - 定位：**个人投研工具**（10 人以内，不做多租户/社区/计费）
> - 数据源：**纯免费**（东方财富 + AkShare + Tushare 积分档 + Finnhub 免费档）
> - 实盘交易：**不做**（专注投研 + 回测，预留券商 API 抽象层即可）
> - 时间：**1-2 月**出 MVP（Tier 1 完整 + Tier 2 子集）

---

## 1. 现状盘点（v0.2.0）

### 1.1 已实现

- 三市场（US / CN / HK）实时行情
- 自选股 CRUD
- 52 周回撤监控 + 阈值告警（webhook 推送）
- 流式批量刷新（task_id + 进度）
- 单只刷新 / 自动刷新
- Toast 通知、CSS 表格布局
- 演示数据兜底（API 失败时）

### 1.2 关键差距

| 维度 | 当前 | 量化平台要求 |
|-----|-----|-------------|
| 图表 | ❌ 无 | K 线 / 多周期 / 叠加指标 |
| 技术指标 | ❌ 无 | 15+ 常用指标（MA/MACD/RSI/BOLL/KDJ/ATR/OBV...） |
| 历史数据 | ❌ 仅当前快照 | 多年 K 线 + 财务 + 估值 |
| 因子库 | ❌ 无 | 估值 / 成长 / 质量 / 动量 / 波动 5 大类 |
| 回测 | ❌ 无 | 事件驱动 + 滑点 + 涨跌停 + 多标的组合 |
| 组合管理 | ❌ 无 | 多股 + 权重 + 再平衡 |
| 风险指标 | ❌ 无 | 夏普 / 最大回撤 / 波动率 / Beta / Alpha / Sortino |
| 基准对比 | ❌ 无 | 沪深300 / 中证500 / 标普500 / 恒生 |
| 策略系统 | ❌ 无 | 至少 5 个内置策略 + 自定义 |
| 模拟交易 | ❌ 无 | Paper Trading（可选） |

**一句话总结**：监控+告警 ✓；投研+回测 ✗。

---

## 2. 对标世界领先平台（已在 web 搜索过 2025-2026 最新对比）

| 平台 | 核心强项 | 我们要对标的具体点 |
|-----|---------|-----------------|
| **QuantConnect (Lean)** | 事件驱动回测引擎、Universe/Alpha/Portfolio/Execution/Risk 五模块、50TB+ 数据、参数优化 | 回测引擎架构、模块化设计 |
| **聚宽 JoinQuant** | A 股分钟/Tick 数据、社区、Notebook、策略库、回测+模拟交易 | A 股数据深度、回测精度、模拟交易 |
| **米筐 RiceQuant** | 多因子、AI 策略生成、RQBeta 风险模型 | 因子库、风险模型 |
| **BigQuant** | AI 驱动、低代码、Stockranker 排名模型 | AI 选股（v2+ 再考虑） |
| **Bloomberg Terminal** | 全球实时数据、图表、新闻、财报、估值、相关性矩阵 | 数据广度、风险/相关性指标 |
| **TradingView** | 最强图表、Pine Script、内置 100+ 指标 | 图表交互、内置指标库 |
| **Alpaca** | 免费美股、Paper Trading、API 优先 | API 抽象层（v2+ 实盘用） |
| **vn.py** | 全开源、多柜台、事件驱动、本地化 | 架构（我们参考，不依赖） |

**5 个核心竞争维度**（业界共识）：
1. **数据深度**（K 线/财务/Level-2/新闻）
2. **回测引擎**（事件驱动、滑点模拟、参数优化）
3. **因子研究**（多因子库、选股、排名）
4. **策略系统**（代码/DSL/拖拽、模拟、实盘）
5. **风控 & 归因**（夏普/回撤/Beta/Alpha、基准对比、行业归因）

我们 v0.2.0 覆盖 0.5/5，目标是 **MVP 覆盖 3.5/5，Tier 2 覆盖 4.5/5**。

---

## 3. 4-Tier 路线图

### Tier 1 — 投研基础（**1-2 月，MVP 范围**）

| 功能 | 说明 | 优先级 |
|-----|-----|------|
| **K 线 + 图表** | lightweight-charts；日/周/月/1/5/15/30/60min 多周期 | P0 |
| **20+ 技术指标** | MA/EMA/MACD/RSI/BOLL/KDJ/ATR/OBV/CCI/WR/BBI/SAR/成交量/换手 | P0 |
| **历史数据层** | SQLite 扩展 kline/daily_metrics/factor_values/portfolios/backtests 表 + 后台入库 | P0 |
| **多因子库** | 估值（PE/PB/PS/PEG）/ 成长（ROE/ROA/增速）/ 质量（毛利率/现金流）/ 动量 / 波动 | P0 |
| **基础回测引擎** | 事件驱动 + 滑点 + 涨跌停 + 多标的组合 | P0 |
| **组合管理** | 多股编辑 + 权重 + 再平衡提醒 | P0 |
| **风险指标 + 基准对比** | 夏普/Sortino/Calmar/最大回撤/波动率/Beta/Alpha；基准：沪深300/中证500/标普500/恒生 | P0 |

### Tier 2 — 平台竞争力（3-5 月，**MVP 完成后追加**）

| 功能 | 说明 | 优先级 |
|-----|-----|------|
| **策略系统** | 5+ 内置策略（双均线/海龟/网格/动量轮动/多因子排名）+ Python 沙箱 | P1 |
| **AI 辅助** | LLM 选股（自然语言 → 因子筛选）+ AI 策略生成 | P1 |
| **模拟交易** | Paper Trading：实时模拟、持仓、归因 | P1 |
| **事件日历** | 财报披露、分红除权、解禁、业绩预告 | P2 |
| **新闻 & 情绪** | AkShare/Tushare 财经新闻 + 基础 NLP 情感 | P2 |
| **多渠道推送** | 飞书/钉钉/微信/邮件/Telegram + 日报/周报 | P2 |
| **自选股分组** | 分组管理 + 分组级回撤阈值 | P2 |

### Tier 3 — 走向世界领先（6-12 月）

| 功能 | 说明 | 优先级 |
|-----|-----|------|
| **实盘交易** | 券商 API 抽象层 + 风控前置 + 灰度（模拟→小资金→全量） | P1（预留接口） |
| **社区** | 策略市场 + 跟单 + 投研文章 | P3 |
| **多账户/多策略** | 私募级账户管理 + 策略并行 + 熔断 | P3 |
| **Level-2 / Tick** | 十档盘口 + 主力资金流 | P3 |
| **全球资产** | 数字货币/外汇/期货/期权 | P3 |

### Tier 4 — 差异化亮点（持续）

- 自然语言投研（跨数据源问答）
- 智能资产配置（风险测评 → 推荐组合）
- 可视化大屏（行业热力图、资金流瀑布）

---

## 4. MVP 1-2 月实施计划

### 4.1 范围（Tier 1 全部 + Tier 2 子集）

✅ **做**：K 线 + 图表 + 15+ 指标 + 历史数据 + 10+ 因子 + 基础回测 + 组合 + 风险 + 基准
⚠️ **可选**（如果进度快）：模拟交易、内置 2-3 个策略模板
❌ **不做**：实盘、AI 选股、社区、Level-2、Tick、新闻、推送扩展

### 4.2 阶段（按周）

| 里程碑 | 时间 | 交付物 |
|-------|-----|--------|
| **M0** | 第 0 周 | 路线图（本文档）+ worktree + DB schema 扩展 + quant_engine 框架 |
| **M1** | 第 1-2 周 | K 线 API + 多周期数据 + 单股图表页（带 MA/成交量） |
| **M2** | 第 2-3 周 | 15+ 技术指标 + 图表叠加指标 |
| **M3** | 第 3-4 周 | 10+ 因子库 + Tushare 财务接入 + 选股器页面 |
| **M4** | 第 4-6 周 | 回测引擎（事件驱动 + 滑点）+ 回测报告页 |
| **M5** | 第 6-7 周 | 组合管理 + 风险指标 + 基准对比 |
| **M6** | 第 7-8 周 | 打磨 / 测试 / 文档 / 错误处理 |

### 4.3 技术选型

| 维度 | 选型 | 理由 |
|-----|-----|-----|
| 后端框架 | FastAPI（已有） | 不变 |
| 数据栈 | **pandas + numpy** | 业界标配，资料多 |
| 图表 | **lightweight-charts** | TradingView 出品，开源、流畅 |
| 回测引擎 | **自研事件驱动** | 不引第三方，参考 Lean 思想 |
| 数据库 | SQLite（已有）+ **DuckDB** 加速分析查询 | 单机起步够用，分析快 10x |
| 任务调度 | APScheduler | 替代裸 Timer，更稳 |
| 财务数据 | Tushare Pro 积分档（免费） | A 股财务最全 |
| A 股实时/历史 | 东方财富（已有）+ AkShare | 免费、K 线全 |
| 美股 | Finnhub（已有） | 维持 |
| LLM（v2+） | 复用已有 MCP | AI 选股再接 |

### 4.4 架构升级

#### 后端

```
backend/
├── main.py              # FastAPI 入口（已有）
├── monitor.py           # 监控（已有）
├── alerter.py           # 告警（已有）
├── data_fetcher.py      # 数据获取（已有）
├── database.py          # DB 基础（扩展 schema）
├── models.py            # Pydantic 模型（扩展）
├── quant_engine/        # ← 新增
│   ├── __init__.py
│   ├── indicators.py    # 15+ 技术指标
│   ├── factors.py       # 10+ 因子
│   ├── backtest.py      # 回测引擎
│   ├── portfolio.py     # 组合管理
│   ├── risk.py          # 风险指标
│   ├── data_source/     # 数据源封装
│   │   ├── akshare_source.py
│   │   ├── tushare_source.py
│   │   └── finnhub_source.py
│   └── api/             # 量化 API 路由
│       ├── kline.py
│       ├── factors.py
│       ├── backtest.py
│       ├── portfolio.py
│       └── risk.py
└── tests/               # 测试（已有 + 新增）
    ├── test_indicators.py
    ├── test_factors.py
    └── test_backtest.py
```

#### 前端

```
frontend/src/
├── pages/
│   ├── Dashboard.jsx        # 监控（已有）
│   ├── Chart.jsx            # ← 新增：单股图表
│   ├── Screener.jsx         # ← 新增：选股器
│   ├── Backtest.jsx         # ← 新增：回测
│   └── Portfolio.jsx        # ← 新增：组合管理
├── components/
│   ├── StockChart.jsx       # lightweight-charts 封装
│   ├── IndicatorPanel.jsx
│   ├── BacktestReport.jsx
│   └── ...
└── lib/
    ├── api.js               # 扩展
    └── indicators.js        # 前端指标（可选，前端只展示）
```

#### DB Schema（扩展）

```sql
-- K 线（OHLCV，多市场多周期）
CREATE TABLE kline (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticker TEXT NOT NULL,
  market TEXT NOT NULL,        -- US / CN / HK
  period TEXT NOT NULL,        -- 1d / 1w / 1mo / 1h / 30m / 15m / 5m / 1m
  trade_date TEXT NOT NULL,    -- YYYY-MM-DD 或 YYYY-MM-DD HH:MM
  open REAL, high REAL, low REAL, close REAL, volume REAL, amount REAL,
  UNIQUE(ticker, market, period, trade_date)
);
CREATE INDEX idx_kline_lookup ON kline(ticker, period, trade_date);

-- 日频估值/财务指标
CREATE TABLE daily_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticker TEXT NOT NULL,
  trade_date TEXT NOT NULL,
  pe_ttm REAL, pb REAL, ps_ttm REAL, peg REAL,
  market_cap REAL, turnover_rate REAL,
  roe REAL, roa REAL,
  revenue_yoy REAL, profit_yoy REAL,
  gross_margin REAL, net_margin REAL,
  debt_ratio REAL, free_cash_flow REAL,
  UNIQUE(ticker, trade_date)
);

-- 因子值（自研因子 / 多因子模型中间产物）
CREATE TABLE factor_values (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticker TEXT NOT NULL,
  trade_date TEXT NOT NULL,
  factor_name TEXT NOT NULL,
  factor_value REAL,
  factor_rank INTEGER,         -- 截面分位排名
  UNIQUE(ticker, trade_date, factor_name)
);

-- 组合
CREATE TABLE portfolios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  benchmark TEXT DEFAULT '000300.SH', -- 沪深 300
  rebalance_freq TEXT DEFAULT 'monthly', -- monthly / quarterly / none
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 组合持仓
CREATE TABLE portfolio_holdings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  portfolio_id INTEGER NOT NULL,
  ticker TEXT NOT NULL,
  weight REAL NOT NULL,        -- 0-1
  added_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
  UNIQUE(portfolio_id, ticker)
);

-- 回测任务
CREATE TABLE backtests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  portfolio_id INTEGER,
  strategy TEXT NOT NULL,       -- 'manual' / 'ma_cross' / 'momentum' / 'factor_rank'
  params TEXT,                  -- JSON: 策略参数
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  initial_capital REAL DEFAULT 1000000,
  commission REAL DEFAULT 0.0003,  -- 万三
  slippage REAL DEFAULT 0.001,     -- 千一
  status TEXT DEFAULT 'pending',  -- pending / running / done / error
  metrics TEXT,                  -- JSON: 收益/夏普/回撤 等
  equity_curve TEXT,             -- JSON: [{date, value}, ...]
  trades TEXT,                   -- JSON: 交易记录
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT
);
```

---

## 5. 关键设计决策

### 5.1 数据源降级策略

```
Tushare Pro（首选，A 股财务）→ AkShare（兜底，免费版）→ 东方财富（已有，实时/历史 K 线）
Finnhub（首选，美股）→ Alpha Vantage（备选）
```

### 5.2 回测引擎选型

- **自研事件驱动**（不引第三方）
- 借鉴 QuantConnect Lean 的设计：Algorithm Framework 分 Universe/Alpha/Portfolio/Execution/Risk
- 我们的简化版：Strategy → Signal → Order → Fill → Portfolio → Equity

### 5.3 涨跌停 & 交易规则

- A 股：±10%（ST ±5%，科创板/创业板 ±20%），T+1
- 港股：无涨跌停，T+0
- 美股：无涨跌停（部分有熔断），T+0

### 5.4 MVP 暂不实现

- **多策略并行**（一个回测一个策略）
- **期权 / 期货**（只做股票 + ETF）
- **实盘下单**（纯回测）
- **AI 选股**（v2+ 再做）

---

## 6. 风险 & 应对

| 风险 | 应对 |
|-----|-----|
| Tushare 积分制限流 | AkShare 兜底；高频调用加缓存 |
| 东方财富接口反爬 | 重试 + 限速 + User-Agent；AkShare 已封装好 |
| lightweight-charts 性能 | 大数据量分批渲染 |
| 1-2 月内完不成 | 砍 Tier 1 子集：先做 K 线+指标+回测，因子 v2 再做 |
| 单人开发质量 | 关键模块写单测（indicators/backtest 必测） |

---

## 7. 验收标准（MVP 收尾）

- ✅ 添加任意股票，能看到 K 线（日/周/月 + 60/30/15/5 分钟）
- ✅ K 线上叠加任意技术指标（MA/MACD/RSI/BOLL/KDJ/ATR 等）
- ✅ 选股器能用 5+ 因子筛选全 A 股，秒级返回 Top N
- ✅ 写一个简单策略（双均线）能跑回测，看收益曲线 + 夏普/回撤
- ✅ 创建多股组合，能跑组合回测，对比沪深 300
- ✅ 风险指标齐全（夏普/最大回撤/波动率/Beta/Alpha）
- ✅ 文档齐全（README + API 文档 + 用户手册）
- ✅ 关键模块测试覆盖（indicators / backtest 80%+）

---

## 8. 参考资料

- QuantConnect Lean 文档：https://www.lean.io/docs
- 聚宽 API：https://www.joinquant.com/help/api/help?name=api
- 米筐文档：https://www.ricequant.com/doc/rqalpha
- TradingView lightweight-charts：https://tradingview.github.io/lightweight-charts/
- Tushare Pro：https://tushare.pro/document/2
- AkShare：https://akshare.akfamily.xyz/

---

> 文档版本：v1.0（2026-06-02）
> 下次更新：MVP M2 完成后（约 2 周后）
