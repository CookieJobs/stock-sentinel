# PRD: 告警通知系统

## 概述

当股票回撤超过阈值时，通过邮件/飞书/钉钉等渠道发送告警通知。

## 背景

目前系统仅在 Dashboard 展示股票数据，用户需要主动查看。当股票大幅回撤时，用户可能错过时机。

## 需求

- 定时检查所有监控股票的 `drawdown_pct` vs `threshold`
- 当 `|drawdown_pct| >= |threshold|` 时触发告警
- 支持多种通知渠道（邮件、飞书机器人、钉钉机器人）
- 告警去重：同一股票 24h 内不重复告警
- 记录告警历史（已发送记录）

## 通知渠道

**站内通知** — 存储告警记录，前端轮询或 WebSocket 推送展示。

配置通过 `.env`：
```
ALERT_ENABLED=true
ALERT_CHECK_INTERVAL=300  # 秒
ALERT_DEDUP_HOURS=24
```

## 告警消息格式

```
[StockSentinel 告警] {ticker} 回撤超限
股票：{name} ({ticker})
市场：{market}
当前回撤：{drawdown_pct}%
阈值：{threshold}%
现价：{current_price}
52W高：{week52_high} ({week52_high_date})
```

```
[StockSentinel 告警] {ticker} 回撤超限
股票：{name} ({ticker})
市场：{market}
当前回撤：{drawdown_pct}%
阈值：{threshold}%
现价：{current_price}
52W高：{week52_high} ({week52_high_date})
```

## 状态机

`needs-triage` → `ready-for-agent` → `wontfix`

## Todo

- [ ] `01-alert-backend.md` — 后端告警核心逻辑
- [ ] `02-alert-frontend-settings.md` — 前端通知渠道配置 UI
- [ ] `03-alert-history.md` — 告警历史记录