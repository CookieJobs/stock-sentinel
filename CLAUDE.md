# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Operating manual**: `AGENTS.md` at the repo root is the AI-maintainer operating
> manual (session ritual, work loop, escalation policy, closing ritual). Read it
> first; this file is the architecture reference.

## Project overview

StockSentinel 是一个**个人投研型量化分析平台**，对标世界领先水平（QuantConnect / 聚宽 / 米筐 / BigQuant）。系统由两大部分组成：

1. **v0.2.0 监控+告警**（原始功能）：自选股管理 + 52 周回撤监控 + 阈值告警
2. **v1.0 量化分析平台**（M0-M5 新增）：K 线图表 + 多因子选股 + 事件驱动回测引擎 + 组合管理 + 风险分析

A React 19 + Vite 前端展示监控仪表盘和量化分析页面；Python FastAPI 后端处理数据获取、持久化、告警与量化计算。

## Quick start

```bash
# 准备 venv（首次）
python3 -m venv .venv --without-pip  # 或直接用 uv venv .venv
.venv/bin/python -m ensurepip --upgrade  # 可选
uv pip install --python .venv/bin/python -r backend/requirements.txt  # 或手动装

# 启动后端
cd backend && ../.venv/bin/python main.py  # → http://localhost:8000

# 启动前端（另一终端）
cd frontend && npm install && npm run dev  # → http://localhost:5173

# 一键启动（推荐）
./start.sh  # 同时启动前后端，访问 http://localhost:5173
```

## Commands

```bash
# Backend
python backend/main.py                  # Start API server on :8000
python -m pytest backend/tests/         # Run all backend tests (137+ tests)
python backend/test_data_fetcher.py     # Run data fetcher smoke tests

# Frontend
cd frontend && npm run dev              # Dev server on :5173, proxies /api → :8000
cd frontend && npm run build            # Build into backend/static/ for production
cd frontend && npm run lint             # ESLint
cd frontend && npm test                 # Vitest (if configured)

# 全栈
./start.sh                              # 同时启动前后端 → 访问 http://localhost:5173
```

开发时只访问 `http://localhost:5173`（Vite proxy 转发 `/api` 到 :8000）。

## Architecture

### Backend (`backend/`)

**核心模块分层**：

```
backend/
├── main.py                  # FastAPI 入口（lifespan 启动 monitor + alerter + briefing + quant_engine）
├── monitor.py               # StockMonitor（v0.2.0 自选股管理 + 刷新 + price_history 采样）
├── alerter.py               # StockAlerter（v0.2.0 52周回撤告警）
├── data_fetcher.py          # DataFetcher（v0.2.0 三市场实时行情）
├── database.py              # 股票/告警 DB
├── models.py                # Pydantic 模型
├── briefing.py              # ⭐ 每日简报（BriefingGenerator + BriefingScheduler，LLM 或模板降级）
├── quant_engine/            # ⭐ v1.0 新增 — 量化分析引擎
│   ├── __init__.py
│   ├── db.py                # 量化相关 DB（kline / daily_metrics / factor_values / portfolios / backtests）
│   ├── indicators.py        # 13 个技术指标（MA/EMA/MACD/RSI/BOLL/KDJ/ATR/SAR/OBV 等）
│   ├── factors.py           # 15 个因子（5 大类：估值/成长/质量/动量/波动）
│   ├── backtest.py          # 事件驱动回测引擎 + 4 个内置信号
│   ├── portfolio.py         # 组合 CRUD + 再平衡检测（M0 基础）
│   ├── risk.py              # 13 个风险指标（夏普/Sortino/Calmar/VaR/Alpha/Beta 等）
│   ├── kline_service.py     # K 线服务（远程拉取 + 本地入库 + LRU 缓存）
│   ├── backtest_service.py  # 异步回测（线程池 + 进度跟踪 + 结果持久化）
│   ├── portfolio_service.py # 组合服务（估值 + 再平衡 + 回测 payload 转换）
│   ├── factor_service.py    # 因子服务（多源拉取 + 截面排名 + 选股）
│   ├── data_source/         # 数据源抽象层
│   │   ├── eastmoney_source.py
│   │   ├── akshare_source.py
│   │   ├── baostock_source.py
│   │   ├── finnhub_source.py
│   │   └── factor_source.py # 因子数据源（Tushare / AkShare / Mock 三级 fallback）
│   └── api/                 # FastAPI 路由
│       ├── kline.py
│       ├── indicators.py
│       ├── factors.py
│       ├── backtest.py
│       ├── portfolio.py
│       ├── risk.py
│       └── metrics.py
└── tests/
    └── quant_engine/        # ⭐ 137 个后端测试
        ├── test_indicators.py   # 27 tests
        ├── test_factors.py      # 17 tests
        ├── test_risk.py         # 17 tests
        ├── test_backtest.py     # 23 tests
        ├── test_portfolio.py    # 24 tests
        └── test_api.py          # 29 tests (集成测试)
```

**v0.2.0 模块说明**（量化分层之上的原始功能）：

- **`monitor.py`** — `StockMonitor`：自选股 CRUD + 后台自动刷新（30s 定时；CN/HK 交易时段
  09:30-16:00 北京时间跳过美股以尊重 Finnhub 限频）+ 单股/批量刷新（`task_id` 进度）。
  同时把真实行情写入 `price_history`（15 分钟桶幂等；demo 数据不落库）。
- **`data_fetcher.py`** — `DataFetcher` 三市场数据管线：US 走 Finnhub（`/quote`、`/stock/metric`、
  `/stock/profile2`，需 `FINNHUB_API_KEY`）；CN 走东方财富 push2 实时 + K 线（52 周高低点由
  最多 300 根日 K 计算，`fltt=1` 价格单位为分/100）；HK 走东方财富 `fltt=2`（价格已正确缩放，
  secid 格式 `116.00xxx`）。CN/HK 东财失败时自动降级腾讯行情（`qt.gtimg.cn` 实时 + `web.ifzq.gtimg.cn`
  日 K 算 52 周高低点，`source=tencent`）。API 全失败或无 key 时回退内置 `DEMO_DATA`。`detect_market()`：
  6 位数字 → CN，1-5 位数字 → HK，`.HK` 后缀 → HK，其余 → US。
- **`alerter.py`** — `StockAlerter` 后台线程（`ALERT_CHECK_INTERVAL`，默认 300s）：逐股检查
  回撤是否超阈值，按 ticker+日期经 `alert_history` 去重，未读告警存 `alert_unread`。
- **`briefing.py`** — 每日简报：`BriefingGenerator` 采集当日快照（`stock_snapshots` 表）→
  组装上下文（含与上一份快照的"昨今对比"）→ 调 LLM（OpenAI 兼容接口，
  `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`）生成 markdown；无 Key 或失败时降级为确定性模板。
  `BriefingScheduler` daemon 线程每 60s 检查，北京时间到点（`BRIEFING_TIME` 默认 08:30）且当日
  未生成则触发；存 `briefings` 表（每天一条，REPLACE）。API：`GET /api/briefings/`、
  `GET /api/briefings/latest`、`GET /api/briefings/{id}`、`POST /api/briefings/generate`。
- **`database.py`** — SQLite at `data/sentinel.db`。建表：`stocks`、`settings`、`alert_history`、
  `alert_unread`、`stock_snapshots`、`briefings`、`price_history`。含 ad-hoc `ALTER TABLE ADD COLUMN` 迁移。
- **`models.py`** — Pydantic v2 模型（`StockResponse`、`AddStockRequest`、`UpdateStockRequest`）。

### Frontend (`frontend/`)

```
frontend/src/
├── App.jsx                  # 根组件（react-router 6 路由）
├── main.jsx                 # 入口
├── index.css                # Tailwind v4 + 主题色变量
├── lib/
│   └── api.js               # API 封装（kline / indicators / factors / backtest / portfolios / risk）
├── components/
│   └── StockChart.jsx       # lightweight-charts 封装（多 pane：主图 + 振荡器）
└── pages/
    ├── Dashboard.jsx        # v0.2.0 监控（保留）
    ├── Chart.jsx            # ⭐ M1 单股图表（K 线 + 指标 + 振荡器）
    ├── Screener.jsx         # ⭐ M3 多因子选股
    ├── Backtest.jsx         # ⭐ M4 回测工作流
    ├── Portfolio.jsx        # ⭐ M5 组合管理
    └── Risk.jsx             # ⭐ M5 风险分析
```

## Data flow

### v0.2.0 监控流
1. User adds stock → `StockMonitor.add_stock()` → `DataFetcher.get_stock_info()` → SQLite
2. Auto-refresh every 30s (CN/HK 全开，US 避开 CN 时段) → 更新 DB
3. `StockAlerter` 每 5min 检一次 → 超阈值写入 `alert_unread`
4. 前端轮询 `/api/stocks/` + `/api/alerts/count`

### v1.0 量化流
1. **选股**：`POST /api/quant/factors/refresh` → 多源拉全 A 股 → 算因子 → 入库
   - 客户端：`POST /api/quant/factors/screen` 多条件筛选 + 排名 → Top N
2. **回测**：`POST /api/quant/backtest/run` → 写 backtests 表 → 后台线程拉 K 线 + 跑引擎
   - 客户端：每 2s 轮询 `GET /api/quant/backtest/{id}` → 拿结果
3. **组合**：`POST /api/quant/portfolios/` 创建 → `POST .../holdings` 加持仓 → `GET .../valuation` 估值
   - 再平衡：`GET .../rebalance` → buy/sell 建议
   - 一键回测：`POST .../run-backtest` → 转 fixed_weights 信号
4. **K 线**：`GET /api/quant/kline/{ticker}` → 远程拉 → 本地 SQLite 缓存 → 返回
5. **风险**：`POST /api/quant/risk/compute` → 13 个指标
6. 前端：lightweight-charts 画 K 线 + 振荡器 pane + 净值曲线 SVG + 回撤曲线

## API endpoints

所有 `/api/quant/*` 路由：

| 端点 | 方法 | 说明 |
|----|----|----|
| `/api/quant/indicators/list` | GET | 列出 13 个指标 |
| `/api/quant/indicators/compute` | POST | 计算指标（payload: {name, params, data}） |
| `/api/quant/factors/list` | GET | 列出 15 个因子 |
| `/api/quant/factors/universe/stats` | GET | Universe 统计（universe_size / factor_count / source） |
| `/api/quant/factors/refresh` | POST | 刷新因子库（多源拉取 + 算因子 + 入库） |
| `/api/quant/factors/industries` | GET | 行业列表（28 个） |
| `/api/quant/factors/screen` | POST | 多条件选股（payload: {filters, rank_by, top_n}） |
| `/api/quant/kline/health` | GET | K 线模块 health |
| `/api/quant/kline/{ticker}` | GET | 获取 K 线（auto-fetch + 缓存） |
| `/api/quant/kline/{ticker}/meta` | GET | K 线元信息 |
| `/api/quant/kline/{ticker}/with-indicators` | POST | K 线 + 指标联合 |
| `/api/quant/kline/cache/clear` | POST | 清 LRU 缓存 |
| `/api/quant/backtest/strategies` | GET | 4 个内置策略 |
| `/api/quant/backtest/run` | POST | 提交回测（异步） |
| `/api/quant/backtest/list/recent` | GET | 最近 N 个回测 |
| `/api/quant/backtest/{id}` | GET | 获取回测状态/结果 |
| `/api/quant/portfolios/` | GET/POST | 组合列表 / 创建 |
| `/api/quant/portfolios/{id}` | GET/DELETE | 获取 / 删除 |
| `/api/quant/portfolios/{id}/holdings` | POST | 加持仓 |
| `/api/quant/portfolios/{id}/holdings/{ticker}` | PUT/DELETE | 更新权重 / 删除 |
| `/api/quant/portfolios/{id}/valuation` | GET | 估值（实时价 + 目标权重） |
| `/api/quant/portfolios/{id}/rebalance` | GET | 再平衡建议（基于阈值 + 资金） |
| `/api/quant/portfolios/{id}/run-backtest` | POST | 一键组合回测 |
| `/api/quant/risk/benchmarks` | GET | 9 个基准（沪深 300/中证 500/标普 500/恒生等） |
| `/api/quant/risk/compute` | POST | 计算 13 个风险指标 |
| `/api/quant/metrics/health` | GET | metrics 模块 health |
| `/api/quant/metrics/dashboard` | GET | Dashboard 综合指标 |

## Key design decisions

### v0.2.0（保留）
- **No ORM** — raw SQL via `sqlite3` with `row_factory = sqlite3.Row`
- **Threading, not async** — 背景 refresh + alert 用 `threading.Thread` / `threading.Timer`
- **Demo data fallback** — 三市场数据 API 失败时回退到内置 `DEMO_DATA`
- **52-week high/low** — 客户端从东方财富 K 线计算（最多 300 根周 K）

### v1.0 新增
- **事件驱动回测引擎**（参考 QuantConnect Lean 思想）：
  - Universe（用 portfolio 代替）→ Alpha（信号）→ Portfolio（持仓）→ Execution（T+0 收盘价 + 滑点 + 涨跌停）→ Risk（M5）
  - 自研，不引第三方（Backtrader / Zipline）
- **多数据源自动降级**：
  - K 线：东方财富 → AkShare → 本地 SQLite
  - 因子：Tushare Pro（首选）→ AkShare → Mock（开发演示）
- **异步回测**（`threading.Thread`）：
  - 提交 → 写 backtests 表 (status=pending) → 后台线程拉数据 + 跑引擎 + 写结果 (status=done)
  - 进度通过 error_msg 字段 hack 写进度文本（v1 简化，v2 改独立列）
- **单选股涨跌停**（A 股）：
  - 主板 ±10%，创业板/科创板 ±20%，ST ±5%（v1 未实现 ST 标识）
  - 港股/美股无涨跌停
- **静态权重组合**（v1 简化）：
  - 当前权重 = 目标权重（无 cash + 持仓股数概念）
  - v2 引入 cash + 持仓股数 + 真实市值计算

## Quant strategy signals（4 个内置）

| 策略 | 适用 | 参数 |
|----|----|----|
| `equal_weight` | 多标的 | - |
| `ma_cross` | 单标的 | `fast` (5), `slow` (20) |
| `factor_rank` | 多标的 | `factor` (momentum_20d / hist_vol_20d), `top_n` (10) |
| `fixed_weights` | 组合回测 | `weights` ({ticker: weight}) |

## Testing

```bash
# Backend（137+ tests）
.venv/bin/python -m pytest backend/tests/ -v

# Frontend（lint + build）
cd frontend && npm run lint && npm run build
```

**测试覆盖**：
- `test_indicators.py` — 13 个指标 + 边界
- `test_factors.py` — 15 个因子 + 注册表一致性
- `test_risk.py` — 13 个风险指标 + 边界（空/单点/常数）
- `test_backtest.py` — 4 个信号 + 涨跌停 + 引擎主流程
- `test_portfolio.py` — CRUD + 估值 + 再平衡 + 回测 payload
- `test_api.py` — 所有 /api/quant/* 路由 + 错误处理

**M6 测试发现并修复的 bug**：
1. RSI 单调上升边界：fillna(50) 改为正确处理 → 强趋势 RSI=100
2. BOLL NaN 比较：std 首项 NaN 容差
3. factor_rank 排名方向：desc 因子（波动率）用 nsmallest 而非 nlargest
4. signal_factor_rank 不识别 hist_vol_20d：加 alias
5. backtest.py 漏 import FACTOR_REGISTRY 报 NameError

## Environment

- **数据源**（env 变量）：
  - `FINNHUB_API_KEY` — 美股（可选，缺失时只回退到本地）
  - `TUSHARE_TOKEN` — Tushare Pro（可选，缺失时用 AkShare 或 Mock）
- **告警配置**：
  - `ALERT_CHECK_INTERVAL` — 默认 300 秒
  - `ALERT_ENABLED` — 默认 true
  - `ALERT_WEBHOOK_URL` — Slack 兼容 webhook（可选）
- **DB**：`data/sentinel.db`（SQLite，WAL 模式）

## Agent skills

### Issue tracker
Local markdown — issues live in `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels
Default vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs
Single-context — `CONTEXT.md` at repo root, `docs/adr/` for architectural decisions. See `docs/agents/domain.md`.

## Roadmap

完整路线图见 `docs/quant-roadmap.md`（v1.0）。

**v1.0 MVP 已完成**（9 commit）：
- ✅ M0 量化引擎骨架
- ✅ M1 K 线 + 单股图表
- ✅ M2 SAR + 振荡器独立面板
- ✅ M3 多因子选股
- ✅ M4 回测工作流
- ✅ M5 组合 + 风险分析
- ✅ M6 打磨（单测 + 端到端 + 文档）

**未来可做**（不在 MVP 范围）：
- Tier 2：策略模板 + AI 辅助 + 模拟交易 + 事件日历
- Tier 3：实盘交易 + 社区 + Level-2
- Tier 4：自然语言投研 + 智能资产配置
