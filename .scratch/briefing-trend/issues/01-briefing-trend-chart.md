# Issue 01: 简报内嵌回撤趋势图

Status: done

## What to build

让每日简报展示「回撤最深的 Top 5」股票的近 30 天回撤走势 sparkline，端到端打通：
后端把 `price_history` 回撤序列写进简报 `stats.trends`；前端简报弹窗用现有 `Sparkline` 组件渲染。

## Acceptance criteria

- [ ] `BriefingGenerator.generate()` 后，`briefings.stats`（JSON）含 `trends` 字段，结构 `[{"ticker","name","market","points":[...]}]`，点数不足 2 的股票被过滤
- [ ] 趋势数据不进 LLM 上下文（LLM 仍用不含 `trends` 的 `ctx`）
- [ ] 前端简报弹窗在正文下方渲染「📉 回撤趋势」小节（复用 `Sparkline`），无数据时该小节不出现、不报错
- [ ] `python3 backend/test_briefing.py` 全部通过（含新增趋势用例）
- [ ] `cd frontend && npm run lint && npm run build` 通过，构建产物同步提交

## Blocked by

None - can start immediately

## Comments

- 2026-08-18：完成（commit dee9fa7 后端 + 291d943 前端）。`BriefingGenerator._load_trends` 读 price_history 回撤序列写入 `stats.trends`（不进 LLM 上下文）；BriefingModal 渲染「📉 回撤趋势」sparkline。`test_briefing.py` 6/6 通过，lint + build 通过。
