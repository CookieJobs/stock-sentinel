# PRD: 简报内嵌回撤趋势图（Briefing Trend Sparkline）

Status: ready-for-agent
Owner: agent
Version: 1.0
Date: 2026-08-18

## Problem Statement

每日简报目前用文字列出「回撤最深的股票」，但看不到这些股票的回撤是**怎么演变**的——是近期快速扩大，还是长期低位震荡。用户想知道"今天回撤 -28% 的票，趋势是恶化还是改善"。历史行情已落库到 `price_history`（`.scratch/price-history/PRD.md`），简报还没有把它用起来。

## Solution

生成简报时，为「回撤最深的 Top 5」股票读取 `price_history` 最近 30 天的回撤序列，存进简报的 `stats.trends`（结构化 JSON）；前端简报弹窗在正文下方渲染这些股票的**回撤 sparkline**（复用现有 `Sparkline` 组件，纯 SVG、无新依赖）。趋势数据只进 `stats`、不进 LLM 上下文（省 token，且 LLM 无法画图）。

## User Stories

1. 作为用户，我想在每日简报里直接看到回撤最深股票的近 30 天回撤走势，以便一眼判断恶化/改善。
2. 作为用户，我希望趋势图在 AI 生成和模板生成两种模式下都可用，以便功能稳定。
3. 作为用户，我希望没有历史数据时不报错、优雅显示占位，以便功能健壮。

## Implementation Decisions

- **后端**（`backend/briefing.py`）：
  - 新增 `BriefingGenerator._load_trends(tickers, days=30)`：按 ticker 查 `price_history` 的 `drawdown` 序列（`ORDER BY bucket ASC`），过滤点数 `< 2` 的股票，保持传入顺序。
  - `generate()` 中：`ctx = build_context(...)` 后调用 `_load_trends([top_drawdowns 的 ticker])` 得到 `trends`；`stats` 落库为 `{**ctx, "trends": trends}`。
  - **LLM 上下文仍用 `ctx`（不含 trends）**，避免把原始点数组喂给模型浪费 token。
  - `trends` 结构：`[{"ticker", "name", "market", "points": [drawdown, ...]}]`。
- **前端**（`frontend/src/components/BriefingModal.jsx`）：
  - 解析 `briefing.stats`（JSON 字符串），若有 `trends` 且非空，在正文下方渲染「📉 回撤趋势」小节，每条 = ticker + 名称 + `<Sparkline points status>`。
  - 复用 `Sparkline.jsx`；`status` 用 `market_status` 色系（alert 红 / warning 黄 / normal 绿，无则灰）。
  - 无 `trends` 或为空时不渲染该小节（不破坏现有布局）。
- **无 schema 变更**：`briefings.stats` 已是 JSON 文本列，直接复用。

## Testing Decisions

- 只测外部行为：`_load_trends` 返回结构、`generate()` 后 `stats.trends` 存在且点数正确、空数据时 `trends` 为空。
- 新增用例并入 `backend/test_briefing.py`（沿用临时 DB 隔离 + 轻量运行器）：先往 `price_history` 插入若干行，再生成简报断言 `stats.trends`。
- 前端：`npm run lint` + `npm run build`。

## Out of Scope

- 简报内嵌 K 线图、多指标趋势（只用回撤 sparkline）。
- 推送渠道、新闻归因（另有 `ready-for-human` issues）。
- 个股详情页趋势（已在 Dashboard 行内实现）。

## Further Notes

- 趋势依赖 `price_history` 采样积累；新部署初期可能点数不足 → 前端不渲染该小节（无感降级）。
- `stats` 已含完整 ctx（市场分布/回撤 Top/超阈值/异动/对比），趋势只是增量字段，向后兼容。

## Todo

- [x] `01-briefing-trend-chart.md` — 后端 stats.trends + 前端 sparkline 渲染
