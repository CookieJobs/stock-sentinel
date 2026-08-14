# StockSentinel — 个人投研型量化分析平台

> 对标世界领先水平（QuantConnect / 聚宽 / 米筐 / Bloomberg）的个人量化分析工具
> 
> **当前版本：v1.0-MVP**（Tier 1 全部 + Tier 2 部分）
> 
> 状态：✅ 6 页面 + 137 后端单测 + 端到端工作流通

---

## ✨ 核心功能

### 📊 监控（v0.2.0 保留）
- 三市场（US / CN / HK）自选股管理
- 52 周回撤监控 + 阈值告警
- 流式批量刷新 + Toast 通知
- Webhook 推送（Slack 兼容）

### 📈 量化分析（v1.0 新增）
| 模块 | 功能 |
|----|----|
| **图表** | K 线（8 周期）+ 成交量 + 13 技术指标（MA/EMA/MACD/RSI/BOLL/KDJ/SAR/OBV 等）+ 振荡器独立 pane |
| **选股** | 15 因子 × 5 大类（估值/成长/质量/动量/波动）× 多条件 AND 筛选 + 排名 |
| **回测** | 事件驱动引擎 + 4 策略（等权/双均线/因子排名/固定权重）+ 滑点 + 涨跌停 + 13 风险指标 |
| **组合** | CRUD + 估值（实时价）+ 再平衡建议 + 一键组合回测 |
| **风险** | 13 指标（夏普/Sortino/Calmar/最大回撤/波动率/VaR/CVaR/Alpha/Beta/信息比率）+ 净值曲线 + 回撤曲线 |

---

## 🚀 快速开始

### 1. 准备环境

```bash
# 创建 venv（用 uv 最快）
uv venv .venv --python 3.12

# 装依赖
uv pip install --python .venv/bin/python \
  fastapi "uvicorn[standard]" pydantic requests python-dotenv \
  pandas numpy scipy duckdb apscheduler akshare tushare pytest httpx
```

### 2. 启动后端

```bash
cd backend
../.venv/bin/python main.py
# → http://localhost:8000
```

后端启动时自动：
- 初始化 SQLite（`data/sentinel.db` + 量化引擎 6 张新表）
- 启动 v0.2.0 自动刷新（每 30s）
- 启动告警检查（每 5min）
- 注册所有 `/api/quant/*` 路由

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Vite dev server 自动 proxy `/api` 到 :8000。

### 4. 一键启动（推荐）

```bash
./start.sh
# 同时启动前后端，访问 http://localhost:5173
```

---

## 📖 使用指南

### 1️⃣ 选股 → 2️⃣ 回测 → 3️⃣ 组合管理

这是核心工作流：

#### Step 1: 选股（页面：选股器）
```
1. 点击"刷新因子库" → 拉全 A 股数据 + 算因子 + 入库（数据源优先级：Tushare → AkShare → Mock）
2. 点击因子按钮（如 "PE-TTM"）+ 调整范围（如 0-30）
3. 选排名方式（如 ROE 降序）
4. 点击"执行选股" → Top N 表格
5. 表格内点"⚡ 回测" → 跳到回测页面预填
```

#### Step 2: 回测（页面：回测）
```
1. 选策略（等权 / 双均线 / 因子排名 / 固定权重）
2. 配参数（如果是双均线：fast=5, slow=20）
3. 输标的代码（逗号分隔）
4. 选起止日期 + 初始资金
5. 点"运行回测" → 自动轮询进度（2s 一次）
6. 完成后看：8 关键指标卡片 + 净值曲线 SVG + 交易记录表
```

#### Step 3: 组合管理（页面：组合）
```
1. 创建组合 + 选基准（沪深 300 / 中证 500 / 标普 500 / 恒生等）
2. 加持仓：代码 + 权重（确保总和 = 100%）
3. 看估值：实时价 × 目标权重 = 模拟总市值
4. 看再平衡：当前 vs 目标偏差 > 阈值就提示 buy/sell
5. 一键组合回测（按持仓权重跑 fixed_weights 策略）
```

### 📈 看 K 线（页面：图表）
```
1. 输代码（600519 / AAPL / 00700）
   → 自动识别市场（A 股 6 位 / 港股 .HK / 美股字母）
2. 选周期（日 K / 周 K / 月 K / 1m / 5m / 15m / 30m / 60m）
3. 选指标预设（MA(5,10,20,60) / BOLL(20,2) / EMA(12,26) / SAR）
4. 选下方振荡器（MACD / RSI / KDJ / WR / CCI / ATR）
5. 鼠标移动看十字光标 OHLC + 所有指标
```

### ⚖️ 风险分析（页面：风险）
```
1. 输入 equity_curve JSON（或从回测历史选择）
2. 自动算 13 个风险指标
3. 切视图：净值曲线 / 回撤曲线 / 风险指标
```

---

## 🧪 测试

```bash
# 后端 137 个单测
.venv/bin/python -m pytest backend/tests/quant_engine/ -v

# 前端 lint + build
cd frontend && npm run lint && npm run build
```

**测试覆盖**：
- 27 个 indicators 测试
- 17 个 factors 测试
- 17 个 risk 测试
- 23 个 backtest 测试
- 24 个 portfolio 测试
- 29 个 API 集成测试

**M6 测试发现并修复的 bug**：
1. RSI 单调上升：原 fillna(50) 错 → 改为正确处理（强趋势=100）
2. BOLL NaN 比较：rolling std 首项 NaN 容差
3. factor_rank 排名方向：desc 因子（波动率）应用 nsmallest
4. signal_factor_rank：加 `hist_vol_20d` 别名
5. backtest.py：缺 import FACTOR_REGISTRY

---

## 🛠️ 数据源（纯免费）

| 市场 | 数据源 | 备注 |
|----|----|----|
| A 股 K 线 | 东方财富 + AkShare | 自动 fallback |
| 港股 K 线 | 东方财富 | - |
| 美股 K 线 | Finnhub | 需 `FINNHUB_API_KEY`（无 key 时返回空） |
| 因子 | Tushare Pro → AkShare → Mock | 需 `TUSHARE_TOKEN` 走真实数据 |

**生产环境配置**：
```bash
export FINNHUB_API_KEY="your_key"  # 可选
export TUSHARE_TOKEN="your_token"  # 可选，配置后用真实全 A 股
```

**测试环境**：Tushare 和 AkShare 远程接口可能被频率限制，**自动 fallback 到 Mock**（3853 只"看似真实"的全 A 股）。

---

## 📁 项目结构

```
stock-sentinel/
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── monitor.py                 # 自选股管理（v0.2.0）
│   ├── alerter.py                 # 告警（v0.2.0）
│   ├── data_fetcher.py            # 行情获取（v0.2.0）
│   ├── database.py                # 股票 DB
│   ├── models.py                  # Pydantic 模型
│   ├── quant_engine/              # ⭐ v1.0 量化引擎
│   │   ├── indicators.py          # 13 技术指标
│   │   ├── factors.py             # 15 因子
│   │   ├── backtest.py            # 事件驱动回测引擎
│   │   ├── portfolio.py           # 组合 CRUD
│   │   ├── risk.py                # 13 风险指标
│   │   ├── kline_service.py       # K 线服务
│   │   ├── backtest_service.py    # 异步回测
│   │   ├── factor_service.py      # 因子服务
│   │   ├── portfolio_service.py   # 组合服务
│   │   ├── data_source/           # 数据源抽象
│   │   └── api/                   # 路由
│   └── tests/quant_engine/        # 137 个测试
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # 根组件 + 路由
│   │   ├── lib/api.js             # API 封装
│   │   ├── components/
│   │   │   └── StockChart.jsx     # 多 pane 图表
│   │   └── pages/
│   │       ├── Dashboard.jsx      # 监控
│   │       ├── Chart.jsx          # 单股图表
│   │       ├── Screener.jsx       # 选股
│   │       ├── Backtest.jsx       # 回测
│   │       ├── Portfolio.jsx      # 组合
│   │       └── Risk.jsx           # 风险
│   └── package.json
├── docs/
│   └── quant-roadmap.md           # 完整路线图
├── data/
│   └── sentinel.db                # SQLite（含 6 张量化表）
├── start.sh                       # 一键启动
├── CLAUDE.md                      # 给 Claude Code 的开发文档
└── README.md                      # 本文件
```

---

## 🔧 API 速查

| 端点 | 说明 |
|----|----|
| `GET /api/health` | 服务 health |
| `GET /api/quant/indicators/list` | 13 指标 |
| `GET /api/quant/factors/list` | 15 因子 |
| `POST /api/quant/factors/refresh` | 刷新因子库 |
| `POST /api/quant/factors/screen` | 多条件选股 |
| `GET /api/quant/kline/{ticker}?market=CN&period=1d` | K 线 |
| `POST /api/quant/kline/{ticker}/with-indicators` | K 线 + 指标 |
| `GET /api/quant/backtest/strategies` | 4 策略 |
| `POST /api/quant/backtest/run` | 提交回测（异步） |
| `GET /api/quant/backtest/{id}` | 轮询/取结果 |
| `POST /api/quant/portfolios/` | 创建组合 |
| `POST /api/quant/portfolios/{id}/holdings` | 加持仓 |
| `GET /api/quant/portfolios/{id}/valuation` | 估值 |
| `GET /api/quant/portfolios/{id}/rebalance` | 再平衡 |
| `POST /api/quant/portfolios/{id}/run-backtest` | 一键组合回测 |
| `POST /api/quant/risk/compute` | 风险指标 |
| `GET /api/quant/risk/benchmarks` | 9 基准 |

完整 API 列表见 `CLAUDE.md`。

---

## 🐛 故障排查

### 后端启动失败
- **No module 'fastapi'**: 装依赖 `uv pip install --python .venv/bin/python fastapi ...`
- **DB locked**: SQLite 单线程访问，关闭其他访问或 `rm data/sentinel.db` 重启

### 前端空白
- **proxy 失败**: 检查 :8000 是否启动，或 `npm run dev` 时 `:5173/api/...` 转发正常
- **控制台红字**: 大概率是后端 500，看 backend 控制台报错

### 选股器显示 0 只
- **数据源未配置**: 缺 `TUSHARE_TOKEN` + AkShare 远程被限 → 自动 fallback 到 Mock（3853 只）
- **因子库没刷新**: 点"🔄 刷新因子库"

### 回测 0 笔交易
- **策略不触发**: ma_cross 单标的 + 短期数据可能没金叉；改更长时间窗口
- **资金不够**: 调小 initial_capital 不足以买入高价股（如茅台 1300 × 100 = 13 万）

### K 线拉不到
- **网络限速**: 东方财富对单 IP 频率敏感 → 等待几秒重试
- **美股 AAPL**: 没 `FINNHUB_API_KEY` → 返回空 row_count=0

---

## 📜 License

MIT
