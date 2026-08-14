# SPEC: 每日简报（Daily Briefing）

Status: ready-for-agent
Owner: agent
Version: 1.0
Date: 2026-05-27（按项目时间线）

## 1. 背景与目标

StockSentinel 目前是一个"被动盯盘"工具：数据展示在 Dashboard 上，用户需要主动打开页面才能看到回撤变化。当监控列表有几十只股票时，靠人肉扫表很难抓住"今天到底发生了什么"。

本功能的目标：**每天早上定时生成一份中文简报**，聚合监控组合的状态与异动，让用户一分钟内掌握：
- 组合整体概况（市场分布、平均回撤、超阈值数量）
- 重点异动（回撤最大的股票、今日涨跌幅最大的股票、新跌破/新脱离阈值的股票）
- 与上一份简报相比的变化（如"回撤从 -20% 扩大到 -28%"）
- 风险提醒与免责声明

这是"模型能力"注入的第一步：**LLM 负责聚合、排序、总结、生成可读文本**；同时提供**无 Key 的模板兜底**，保证功能在未配置任何 LLM 时也可用。

## 2. 非目标（v1 不做）

- ❌ 不做预测、不给买卖建议（输出强制带免责声明）
- ❌ 不做新闻抓取与单股归因（下一迭代）
- ❌ 不做推送渠道（飞书/邮件），简报先站内展示 + 可手动生成（推送留接口）
- ❌ 不引入新 Python/前端依赖（LLM 用已有的 `requests` 调 OpenAI 兼容接口；前端用轻量 markdown 渲染器，不引 react-markdown）
- ❌ 不重构现有告警逻辑

## 3. 架构总览

```
┌─────────────┐   每 60s 检查     ┌──────────────────┐
│ Briefing    │ ───────────────▶ │ BriefingGenerator │
│ Scheduler   │  到点且今日未生成  │  ① collect_snapshot │
└─────────────┘                   │  ② build_context   │
        ▲                         │  ③ generate        │
        │ 触发                     │     ├─ LLM 模式     │
┌───────┴────────┐                │     └─ 模板兜底     │
│ POST /api/     │                │  ④ 落库 briefings  │
│ briefings/     │                └──────────────────┘
│ generate       │                         │
└────────────────┘                         ▼
                                   SQLite: stock_snapshots / briefings
```

- 调度与手动触发都走同一个 `generate()` 入口，幂等（同一天 REPLACE）。
- 生成前把当天全部股票快照写入 `stock_snapshots`（含昨日对比所需的上一份快照）。
- LLM 失败（无 Key / 网络错 / 超时 / 非 200）→ 自动降级模板模式，记录日志，不阻塞。

## 4. 数据模型（`backend/database.py` 新增）

```sql
CREATE TABLE IF NOT EXISTS stock_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,        -- YYYY-MM-DD（北京时间）
    ticker TEXT NOT NULL,
    name TEXT,
    market TEXT,
    current_price REAL,
    change_pct REAL,
    drawdown REAL,
    week52_high REAL,
    threshold REAL,
    UNIQUE(snapshot_date, ticker)
);

CREATE TABLE IF NOT EXISTS briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_date TEXT NOT NULL UNIQUE, -- YYYY-MM-DD（北京时间）
    title TEXT NOT NULL,
    content TEXT NOT NULL,              -- markdown 文本
    mode TEXT NOT NULL DEFAULT 'template',  -- 'llm' | 'template'
    stats TEXT,                         -- JSON 结构化统计（排序、对比等，供调试/前端）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

约定：
- 日期一律用**北京时间**（`UTC+8`）计算。
- 快照与简报以"天"为单位；同一天多次生成 → `INSERT OR REPLACE`，不产生重复行。
- `stats` 存结构化摘要（Top 回撤列表、超阈值列表、昨今对比），即使 LLM 生成失败也能从模板结果里看到数据。

## 5. 后端实现

### 5.1 新模块 `backend/briefing.py`

**`BriefingGenerator`（核心）**
- `collect_snapshot(date)` — 读 `stocks` 全表 → 写 `stock_snapshots`（REPLACE）。
- `load_previous_snapshot(date)` — 取 `snapshot_date < date` 的最新一天快照，用于昨今对比。
- `build_context(date, prev_date)` — 组装结构化数据：
  - 当日快照（市场分布、平均回撤、Top N 回撤、超阈值清单、今日涨跌 Top N）
  - 昨今对比（每只股票 drawdown/价格 的变化，最多列出明显变化的若干条）
  - 今日告警数（`alert_unread` 当日新增数，可省——先取未读数）
- `generate(date)` — 入口：
  1. `collect_snapshot`
  2. `build_context`
  3. 尝试 LLM（有 Key 时）→ 成功则 `mode='llm'`；否则模板 → `mode='template'`
  4. `INSERT OR REPLACE INTO briefings`
  5. 返回 `{briefing, mode}`（briefing 为完整记录 dict）
- `_call_llm(system, user)` — 纯函数化，方便 mock 测试：
  - `POST {LLM_BASE_URL}/chat/completions`，`requests` 超时 60s
  - body: `{model, messages, temperature: 0.3, max_tokens: 1200}`
  - 解析 `choices[0].message.content`；任何异常/非 200 → 返回 `None`

**`generate_template(context)`** — 确定性文本：
```
# 📰 StockSentinel 每日简报（YYYY-MM-DD）

## 📊 组合概况
- 监控 X 只：美股 a / A股 b / 港股 c；平均回撤 -x.xx%
- 超过阈值的股票：n 只（列表）

## 🔻 回撤最深的 5 只
1. TICKER 名称（市场）-x.xx%（现价 ¥/HK$/US$ xxx，52W高 xxx）
...

## ⚡ 今日异动
- 涨幅最大：…；跌幅最大：…
- 较上一份简报变化明显的股票（如有多份快照）

## ⚠️ 风险提醒与免责声明
本简报由 StockSentinel 自动生成，仅基于监控数据汇总，不构成任何投资建议。
```

**`BriefingScheduler`（调度线程）**
- daemon 线程，每 60s 醒来一次；`BRIEFING_ENABLED != 'true'` 时不启动。
- 触发条件：北京时间 `now >= BRIEFING_TIME`（默认 `08:30`）且 `briefings` 表中无当日记录。
- 触发后调用 `generate()`；异常 catch 后记日志，线程不死。
- `stop()` 用 `threading.Event` 干净退出（对齐 `monitor.py`/`alerter.py` 的既有风格）。

### 5.2 `backend/main.py`

- lifespan 中启动/停止 `BriefingScheduler`（在 alerter 之后）。
- 新端点（注意 `/latest` 定义在 `/{id}` 之前）：
  - `GET /api/briefings/` — 历史列表（id, briefing_date, title, mode, created_at，按日期倒序）
  - `GET /api/briefings/latest` — 最新简报全文；无则 404
  - `GET /api/briefings/{briefing_id}` — 按 id 取单条
  - `POST /api/briefings/generate` — 手动立即生成，返回 `{briefing, mode}`

### 5.3 配置（`.env` / `.env.example`）

```
BRIEFING_ENABLED=true
BRIEFING_TIME=08:30            # 北京时间，HH:MM
LLM_API_KEY=                   # 留空 → 模板模式
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

### 5.4 Prompt 设计

- **system**：你是 StockSentinel 的个人投研助手。你只会获得一份结构化 JSON 监控数据。请用简体中文输出一份 markdown 简报：分「组合概况 / 重点异动 / 风险提醒」三节；只依据给定数据，不编造；文末必须包含免责声明"本简报由 AI 自动生成，仅供信息参考，不构成投资建议"。
- **user**：JSON 数据 + 输出要求（重点突出回撤扩大、新超阈值、大跌个股；变化不明显时如实说明）。
- `temperature=0.3` 压低发散，`max_tokens=1200` 控制成本。

## 6. 前端实现

### 6.1 新组件 `frontend/src/components/BriefingModal.jsx`

- 打开时并行拉取 `/api/briefings/latest` 与 `/api/briefings/`（历史列表）。
- 头部：标题 + mode 徽标（`AI 生成` / `模板生成`）+ 生成时间。
- 正文：**轻量 markdown 渲染器**（不引依赖）：
  - `# / ## / ###` 标题 → 分级字号
  - `- ` 列表项 → 圆点列表
  - `**bold**` → `<strong>`
  - 空行分段；其余按 `whitespace-pre-wrap` 文本展示
- 底部：`🔄 立即生成` 按钮（POST，生成中禁用+转圈）、历史日期列表（点击切换查看某天简报）。
- 出错/空状态：友好提示（"暂无简报，点击立即生成"）。

### 6.2 `Dashboard.jsx`

- 头部按钮区加 `📰 简报` 按钮（放在"告警"旁），打开弹窗。
- 不引入路由，保持单页弹窗模式（与现有告警面板一致）。

## 7. 错误处理与边界

| 场景 | 行为 |
|---|---|
| 无 `LLM_API_KEY` | 模板模式，`mode='template'` |
| LLM 调用失败/超时/非 200 | 降级模板模式，日志记录原因 |
| 监控列表为空 | 简报正常生成，内容提示"暂无监控数据" |
| 无昨日快照 | 只输出当日，对比节省略 |
| 调度线程异常 | catch + 日志，线程继续跑 |
| 同一天多次生成 | REPLACE，保持每天一条 |
| 手动生成与自动生成竞争 | SQLite REPLACE 幂等，无重复行 |

## 8. 测试（`backend/test_briefing.py`）

沿用现有 `test_data_fetcher.py` 的轻量风格（无 pytest 依赖，`if __name__ == "__main__"` 直接跑）：

1. `collect_snapshot` 写入且幂等（同一天两次不重复）
2. `generate_template` 输出包含"免责声明"、监控数量、超阈值清单
3. `_call_llm` 在坏 URL / 无 Key 时返回 `None`（不抛异常）
4. API 冒烟：`/api/briefings/generate` → `/api/briefings/latest` → 列表（用 FastAPI TestClient，跑在隔离的临时 DB 上，避免污染真实数据）

## 9. 里程碑

- **M1** Spec + DB 迁移 + `briefing.py`（快照/模板/LLM/生成器）
- **M2** `main.py` 调度接入 + API 端点 + `.env.example`
- **M3** 前端 `BriefingModal` + Dashboard 入口
- **M4** 测试跑通 + 前端构建 + `CLAUDE.md` 更新 + 端到端验证

## 10. 后续迭代（不在本 Spec 范围）

- 新闻归因（大跌时自动拉新闻 → LLM 总结原因附在简报/告警里）
- 推送渠道（飞书/Lark、邮件）
- 简报内嵌图表（回撤趋势线，需历史行情落库）
- 自然语言查询（NL → 结构化筛选）
