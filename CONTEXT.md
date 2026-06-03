# CONTEXT.md — 项目状态快照

> **30 秒读完**，新会话或新 AI 接手时**先看这个**。
> 详细架构看 `CLAUDE.md`，开发历程看 `.claude/PROJECT_HISTORY.md`，待办看 `.claude/TODO.md`。

---

## 🎯 项目是什么

**StockSentinel** — 个人投研型量化分析平台

| 维度 | 状态 |
|----|----|
| 用户 | 一个人（项目所有者，做投资/交易多）|
| 定位 | 对标世界领先水平（QuantConnect / 聚宽 / 米筐 / BigQuant）|
| 范围决策 | 个人工具 / 纯免费数据源 / 不做实盘 |
| 商业模式 | 无（自用）|
| License | MIT |

**前身** v0.2.0 = 监控 + 告警（52 周回撤）
**当前** v1.0-MVP = 量化分析平台（K线 + 选股 + 回测 + 组合 + 风险）

---

## 🏗️ 技术栈（一行清单）

- **后端**：Python 3.12 + FastAPI + SQLite + pandas/numpy/scipy + DuckDB + APScheduler
- **前端**：React 19 + Vite + Tailwind v4 + lightweight-charts + react-router
- **量化引擎**：自研事件驱动（参考 QuantConnect Lean 思想）
- **数据源**：东方财富 + AkShare + Tushare（需 200 积分）+ yfinance（**已失效**，2024-2025 被封锁）+ BaoStock

---

## 📂 目录速查

```
/Users/liujin/Documents/myCraft/stock-sentinel/
├── backend/
│   ├── main.py               # FastAPI 入口
│   ├── monitor.py, alerter.py, data_fetcher.py  # v0.2.0 监控（保留）
│   ├── database.py, models.py
│   ├── quant_engine/         # ⭐ v1.0 核心
│   │   ├── indicators.py     # 13 指标
│   │   ├── factors.py        # 15 因子
│   │   ├── backtest.py       # 事件驱动回测
│   │   ├── portfolio.py      # 组合 CRUD
│   │   ├── risk.py           # 13 风险指标
│   │   ├── kline_service.py  # K 线 + 缓存
│   │   ├── backtest_service.py  # 异步回测
│   │   ├── factor_service.py    # 多源拉取 + 选股
│   │   ├── portfolio_service.py
│   │   ├── data_source/      # 多源抽象
│   │   └── api/              # FastAPI 路由
│   └── tests/quant_engine/   # 137 个单测
├── frontend/src/
│   ├── App.jsx               # 6 路由
│   ├── lib/api.js
│   ├── components/StockChart.jsx
│   └── pages/                # 6 页面
├── data/sentinel.db          # SQLite（含 6 张量化表）
├── docs/
│   ├── quant-roadmap.md      # 路线图
│   ├── agents/               # ⭐ AI 文档
│   └── adr/                  # ⭐ 架构决策
├── .claude/                  # ⭐ Claude Code 专属
├── start.sh                  # 一键启动
├── CLAUDE.md                 # 架构 + API 速查
├── README.md                 # 用户手册
└── CONTEXT.md                # ⭐ 你正在看的
```

---

## 🚀 快速运行

```bash
# 后端（占 8000）
cd backend && ../.venv/bin/python main.py

# 前端（占 5173，proxy /api → 8000）
cd frontend && npm install && npm run dev

# 一键
./start.sh
# → http://localhost:5173
```

---

## ⚠️ 关键约束（碰了会炸）

1. **worktree 模式**：**不要在 main checkout 改代码**——所有改动都在 `.worktrees/feat-xxx/` 里
2. **Python 3.14 venv ensurepip 不兼容** —— 用 Python 3.12
3. **测试环境数据源被限流** —— 东方财富/AkShare/BaoStock/yfinance 都封了测试 IP
4. **Tushare 100 积分不能调任何 Pro 接口** —— 至少 200 积分
5. **前端 lint 有 3 个 react-hooks 警告**（Dashboard.jsx 旧代码）—— 已用 `eslint-disable` 压住

---

## 🧪 质量门

```bash
.venv/bin/python -m pytest backend/tests/quant_engine/ -q    # 137 测
cd frontend && npm run lint && npm run build               # 0 errors, 486KB
```

**任何 commit 前必须跑过这两个**。

---

## 📊 当前状态速览（2026-06-03）

| 维度 | 状态 |
|----|----|
| 6 页面 | ✅ 监控 / 图表 / 选股 / 回测 / 组合 / 风险 |
| 13 指标 + 15 因子 + 4 策略 | ✅ |
| 137 后端测试 | ✅ 5 个真 bug 已修 |
| 5524 只 A 股真实代码入库 | ✅ AkShare fallback |
| PE/PB 估值数据 | ⚠️ 等 Tushare 200 积分（5 分钟）|
| 10+ 年长历史 K 线 | ⚠️ 等 BaoStock 接入（30 分钟）|
| 美股 / 港股 | ⚠️ 等 Tushare 200 积分 |
| CI/CD | ❌ 手动跑测试 |
| 部署到生产 | ❌ 自用，无需 |

---

## 🤝 接手 AI 的 5 步

1. **读** `CONTEXT.md`（你已读了）
2. **读** `CLAUDE.md` 的"Architecture"段（10 分钟）
3. **跑** `./start.sh`，浏览器把 6 页面过一遍（5 分钟）
4. **跑** `pytest backend/tests/quant_engine/ -q` 确认 137 都过
5. **改代码前** 读 `.claude/PROJECT_HISTORY.md` 的"教训"段

新工作流 → 建 worktree → 改 → 测 → commit → push → PR。
