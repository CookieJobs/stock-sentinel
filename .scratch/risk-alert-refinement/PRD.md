# PRD: 风险关注提醒优化

Status: ready-for-agent
Owner: agent
Version: 1.0
Date: 2026-08-26

## Problem Statement

现有功能把「相对 52 周最高点的回撤」直接当作每日告警条件：同一股票每天最多一条，但持续超限时会每天重复提醒。它既无法表示用户是否主动启用提醒，也没有「恢复后重新布防」的状态，导致告警疲劳。

阈值的数据语义也不一致：界面输入正数百分比，后端却只认负数；编辑保存会将已启用的提醒实际关闭。单一回撤值还可能来自过期或异常行情，因此不应在未校验的情况下推送。

## Goal

将现有功能收敛为可信、低噪音、可解释的「单股风险关注提醒」：提醒用户关注风险边界，而不输出买卖指令。

## User Stories

1. 作为用户，我能明确地为每只股票开启或关闭 52 周高点回撤提醒，并以正数百分比设置阈值。
2. 作为用户，我只会在首次越过回撤线时收到提醒；股票明显恢复后才会重新布防。
3. 作为用户，我能在历史记录中看到触发时的回撤、阈值和触发原因，而不是只有代码与日期。
4. 作为用户，我不会因为明显异常或长期未更新的行情收到误导性提醒。

## Product Decisions

- **定位**：52 周回撤是关注信号，不是止损、买卖或策略执行信号。组合最大回撤、成本价止损和策略条件监控不在本期范围。
- **配置语义**：`threshold` 统一存为正数百分比，`alert_enabled` 独立开关。新股票默认关闭提醒，预填 15%。
- **兼容迁移**：既有负数阈值迁移为「开启 + 绝对值」；既有零和正数阈值迁移为「关闭」。不删除或重写 `alert_history` 既有记录。
- **状态机**：`armed` 状态在 `drawdown <= -threshold` 时触发一次并转为 `breached`；只有回撤收窄到 `-(threshold - 2pp)` 以上才回到 `armed`。恢复本身不打扰用户。
- **数据防线**：没有回撤/阈值、提醒关闭、回撤低于 -95%、或行情时间超过 120 分钟时不触发。120 分钟可由 `ALERT_MAX_QUOTE_AGE_MINUTES` 覆盖。
- **去重**：保留同 ticker、同自然日最多一条历史记录，作为状态机之外的最后保护；状态机消除持续超限的每日重复告警。

## Solution

### Backend

- `stocks` 表新增 `alert_enabled`；新增 `alert_state` 保存每只股票是否已处于 breach 状态、最近回撤、触发/恢复时间。
- `alerter.py` 用状态机判定首次越线和恢复，保留既有站内未读和可选 webhook 通道。
- `alert_history` 追加触发快照列（事件类型、触发回撤、阈值），新记录完整，旧记录允许为空。
- 统一返回 `alert_enabled`，并在 `StockMonitor` 写入时规范化阈值为正数。

### Dashboard

- 新建和编辑弹窗提供显式「启用 52 周回撤提醒」开关；关闭时阈值输入禁用。
- 表格阈值列明确显示「未启用」，不再以 `0%` 误导用户。
- 未读和历史告警显示「首次越线」及回撤/阈值快照；文案明确为关注提醒。

## Testing Decisions

- 新增 `backend/test_alerter.py`，临时 SQLite 数据库测试正数阈值、首次越线仅告警一次、恢复后重新布防、异常/过期行情抑制和历史快照。
- 前端以 `npm run lint` 与 `npm run build` 验证类型、语法及构建产物。
- 全量运行 `python backend/test_data_fetcher.py` 与 `python -m pytest backend/tests/ -q`，避免破坏行情和量化模块。

## Out of Scope

- 成本价止损、追踪止损、组合最大回撤、VaR、仓位漂移提醒。
- 策略定时扫描、策略信号告警和真实交易执行。
- 新增付费推送服务或修改用户的 webhook / 凭据配置。

## Todo

- [x] `01-alert-backend-state.md` — 数据兼容、状态机、数据防线与测试
- [x] `02-alert-dashboard-config.md` — 显式开关、告警解释与前端构建
- [x] 全量验证、CHANGELOG 与收工记录

## Comments

- 2026-08-26：完成。旧的负数阈值自动迁移为正数阈值并开启提醒，零阈值保持关闭；未删除历史记录。
- 验证：`backend/test_alerter.py` 7/7、`backend/test_briefing.py` 6/6、`test_data_fetcher.py` 全过；量化测试排除受沙箱限制的 Tushare 文件写入后 229 passed；前端 lint/build 通过。
