# Domain — StockSentinel 项目领域

> 给 AI 快速理解这个项目**做什么、谁用、什么数据流、关键名词**。
> 重写自 v0.2.0 版本，反映 v1.0 量化平台实际状态。

---

## 🎯 一句话

**StockSentinel = 个人投研型量化分析平台**（v1.0 量化平台，v0.2.0 是它的"监控+告警"前身）。

用户：一个人（项目所有者，做投资/交易）
目标：让用户能**用真实数据做日常投研**：看 K 线、筛票、回测、跑组合、分析风险。

---

## 🏛️ 核心概念

### 数据相关
| 名词 | 含义 |
|----|----|
| **Ticker** | 股票代码（A 股 6 位数字 / 港股 5 位数字 / 美股字母）|
| **Market** | 市场：`US` / `CN` / `HK` |
| **K 线** | 单只股票 OHLCV 时序数据（Open/High/Low/Close/Volume）|
| **Period** | K 线周期：`1d` 日 K / `1w` 周 K / `1m` 月 K / `5m` 5 分钟 K 等 |
| **Adj** | 复权方式：`qfq` 前复权 / `hfq` 后复权 / `none` 不复权 |
| **Indicator** | 技术指标（MA/MACD/RSI 等 13 个）|
| **Factor** | 截面因子（PE/PB/ROE 等 15 个）|
| **Universe** | 全 A 股代码池（当前 5524 只）|
| **Benchmark** | 基准指数（沪深 300 / 中证 500 / 标普 500 / 恒生 等 9 个）|

### 业务相关
| 名词 | 含义 |
|----|----|
| **Screener（选股器）** | 多条件筛选 + 排名 → Top N |
| **Backtest（回测）** | 用历史 K 线模拟策略执行，算收益 + 风险 |
| **Strategy（策略）** | 4 个内置：等权 / 双均线 / 因子排名 / 固定权重 |
| **Portfolio（组合）** | 多只股票 + 权重 |
| **Valuation（估值）** | 当前价 × 持仓权重 → 总市值 |
| **Rebalance（再平衡）** | 当前权重 vs 目标权重偏差 > 阈值 → 触发调仓 |
| **Drawdown（回撤）** | 净值从峰值下跌的幅度 |
| **Sharpe / Sortino / Calmar** | 风险调整收益指标 |
| **Alpha / Beta** | 相对基准的超额 / 跟随程度 |

### 技术相关
| 名词 | 含义 |
|----|----|
| **Quant engine** | 后端自研模块 `backend/quant_engine/`（自包含）|
| **Data source** | 拉取外部数据的抽象层（多源 fallback）|
| **Worktree** | Git 分支隔离工作区（项目强制用）|
| **Mock** | 项目里"假数据源"——开发演示用，包含 3853 只"假"但行业分布真实的 A 股 |
| **Tier** | 路线图分层（Tier 1 基础 / Tier 2 竞争力 / Tier 3 领先 / Tier 4 差异化）|
| **MVP** | Minimum Viable Product（v1.0 已达成）|

---

## 🗺️ 6 大页面

| 页面 | 路径 | 用户做什么 |
|----|----|----|
| **监控 (Dashboard)** | `/` | 看自选股实时价 + 52 周回撤 + 告警（v0.2.0 保留）|
| **图表 (Chart)** | `/chart` | 看单只 K 线 + 13 指标 + 振荡器 pane |
| **选股 (Screener)** | `/screener` | 多条件筛全 A 股 → Top N 票 |
| **回测 (Backtest)** | `/backtest` | 提交策略 + 配参数 + 跑回测 → 看指标 |
| **组合 (Portfolio)** | `/portfolio` | 创建组合 + 加持仓 + 估值 + 再平衡 + 一键回测 |
| **风险 (Risk)** | `/risk` | 输入净值曲线 → 13 指标 + 净值/回撤曲线 |

---

## 🔄 核心工作流（投资人实际会用到的）

```
[1] 选股 — Screener
    输入: PE < 30, ROE > 15%, 行业=消费, 排名=ROE 降序
    输出: Top 10 票
        ↓
[2] 一键回测 — Backtest
    输入: 上面 10 票 + 起始日期 1 年 + ma_cross 策略
    输出: 总收益 5%, 夏普 1.2, 最大回撤 8%, Alpha 2%
        ↓
[3] 入选组合 — Portfolio
    创建组合 "成长组合"
    入选上面 5 票, 各 20% 权重
        ↓
[4] 监控 — Portfolio / Dashboard
    看组合估值 (当前价 × 权重)
    看再平衡建议 (当前权重 vs 目标权重)
        ↓
[5] 风险分析 — Risk
    拉回测结果 → 13 风险指标 + 净值曲线 + 回撤曲线
```

**这 5 步是投资人日常循环**。v1.0-MVP 完整支持。

---

## 📊 数据流

```
外部数据源
  ├── Tushare Pro (官方, 200 积分档)
  ├── AkShare (开源)
  ├── 东方财富 (直接 REST)
  ├── BaoStock (通联, REST)
  └── (Mock - 假数据)
        ↓
   data_source/ (抽象层, 自动 fallback)
        ↓
   持久化
  ├── kline 表 (OHLCV)
  ├── daily_metrics 表 (PE/PB/财务)
  └── factor_values 表 (因子排名)
        ↓
   服务层
  ├── kline_service (拉 + 入库 + 缓存)
  ├── factor_service (拉全 A 股 + 算因子 + 选股)
  ├── backtest_service (异步跑回测)
  └── portfolio_service (估值 + 再平衡)
        ↓
   API 层 (FastAPI /api/quant/*)
        ↓
   前端 (React)
  ├── Chart.jsx (lightweight-charts)
  ├── Screener.jsx (筛选 UI)
  ├── Backtest.jsx (回测工作流)
  ├── Portfolio.jsx (组合管理)
  └── Risk.jsx (风险分析)
```

---

## 🚫 已知边界

- **不做**：实盘交易、社区、Level-2、加密货币、外汇、商品（Tier 3+ 才考虑）
- **付费数据**：用户范围决策排除（除非用户主动开通）
- **生产部署**：单用户自用，无需 K8s / Docker / 多租户
- **移动端**：v1 不做（PC 端优先）

---

## 📚 关键文档

- `CLAUDE.md` — 架构 + API 速查
- `README.md` — 用户使用手册
- `docs/quant-roadmap.md` — 完整路线图（Tier 1-4）
- `.claude/PROJECT_HISTORY.md` — 开发历程
- `.claude/TODO.md` — 当前待办
- `docs/adr/` — 架构决策记录
