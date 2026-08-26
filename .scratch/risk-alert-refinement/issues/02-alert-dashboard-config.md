# Issue 02: Dashboard 风险关注配置与历史说明

Status: done

## Scope

- 添加/编辑股票的显式提醒开关。
- 关闭时不提交为隐式 `0%`，阈值使用正数百分比。
- 监控表、未读与历史告警显示启用状态和触发快照。

## Acceptance

- 用户可独立控制提醒开关。
- 未启用项显示「未启用」。
- `npm run lint` 和 `npm run build` 成功。

## Comments

- Dashboard 现在以显式开关控制提醒，正数阈值统一为「关注线」；未启用项、首次越线和历史快照均可见。
- `npm run lint`、`npm run build` 通过，构建产物已同步。
