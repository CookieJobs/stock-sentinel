# Issue 01: 回撤提醒状态机与数据防线

Status: done

## Scope

- 正数阈值 + `alert_enabled` 的兼容迁移。
- 首次越线触发、恢复后重新布防、同日历史去重。
- 过期/异常行情抑制，历史写入触发快照。
- `backend/test_alerter.py` 覆盖可观测行为。

## Acceptance

- 编辑使用正数阈值后仍可触发提醒。
- 持续超限不会增加未读或历史；恢复再越线可重新进入触发路径。
- `drawdown <= -95` 与超过新鲜度上限的数据不会触发。

## Comments

- 新增 `alert_enabled`、`alert_state`、历史触发快照和 120 分钟行情新鲜度保护；恢复超过 2pp 后重新布防。
- `backend/test_alerter.py` 7/7 通过，含旧库阈值迁移和删除后状态清理验证。
