# CONTEXT.md — 项目状态快照

> 完成 `AGENTS.md` 规定的 `CONSTITUTION.md` 强制加载门后，用 **30 秒读完**这份项目快照。
> 详细架构看 `CLAUDE.md`；工程操作与完整质量门仅以 `docs/agents/engineering-playbook.md` 为准。

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
/Users/liujin/Documents/stock-sentinel/
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
│   └── tests/quant_engine/   # 量化引擎测试
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
├── start.sh                  # 一键启动
├── CLAUDE.md                 # 架构 + API 速查
├── CONSTITUTION.md           # ⭐ 稳定产品与治理原则
├── AGENTS.md                 # ⭐ AI 加载与执行契约
├── README.md                 # 用户手册
└── CONTEXT.md                # ⭐ 你正在看的
```

AI 文档与工程参考：

- `docs/agents/engineering-playbook.md` — 代码、测试、构建、Git 与交接操作
- `docs/agents/issue-tracker.md` — 事项格式与状态
- `docs/agents/triage-labels.md` — 事项标签
- `docs/agents/domain.md` — 领域术语扩展
- `docs/quant-roadmap.md` — 量化路线图
- `docs/adr/` — 架构决策记录

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

## ⚠️ 当前环境提示

1. **Python 3.14 venv ensurepip 不兼容** —— 用 Python 3.12
2. **测试环境数据源被限流** —— 东方财富/AkShare/BaoStock/yfinance 都封了测试 IP
3. **Tushare 100 积分不能调任何 Pro 接口** —— 至少 200 积分
4. **前端 lint 有 3 个 react-hooks 警告**（Dashboard.jsx 旧代码）—— 已用 `eslint-disable` 压住

---

## 🧪 工程验证入口

worktree 使用政策、开发命令与 commit 前完整质量门统一维护在
`docs/agents/engineering-playbook.md`；本快照不复制易失效的命令、数量或产物大小。

---

## 📊 当前状态速览（2026-06-03）

| 维度 | 状态 |
|----|----|
| 6 页面 | ✅ 监控 / 图表 / 选股 / 回测 / 组合 / 风险 |
| 13 指标 + 15 因子 + 4 策略 | ✅ |
| 后端测试 | ✅ 当前完整测试集通过；精确结果见 `CHANGELOG.md` 最新记录 |
| 5524 只 A 股真实代码入库 | ✅ AkShare fallback |
| PE/PB 估值数据 | ⚠️ 等 Tushare 200 积分（5 分钟）|
| 10+ 年长历史 K 线 | ⚠️ 等 BaoStock 接入（30 分钟）|
| 美股 / 港股 | ⚠️ 等 Tushare 200 积分 |
| CI/CD | ❌ 手动跑测试 |
| 部署到生产 | ❌ 自用，无需 |

---

## 🤝 接手 AI 的 5 步

1. **读** `CONSTITUTION.md`（稳定产品与治理原则）
2. **读** `CONTEXT.md`（本项目快照与领域入口）
3. **读** `AGENTS.md`（AI 运行契约）
4. **读** `CLAUDE.md` 的"Architecture"段与 `docs/agents/engineering-playbook.md`（代码工作指南）
5. 按任务需要阅读当前 PRD、issues、ADR、领域文档与量化路线图

新工作按 `AGENTS.md` 的“模式 B 工作循环”推进；Git、worktree、验证与提交细节以工程手册为准。
