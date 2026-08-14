# Issue 01: 后端告警核心逻辑

Status: done

## 描述

实现告警检查核心逻辑（站内通知）：
1. 定时轮询所有股票，比较 `drawdown` vs `threshold`
2. 触发条件：`abs(drawdown) >= abs(threshold)` 且 `threshold < 0`
3. 去重逻辑：同一 ticker 每天不重复告警（SQLite 表记录）
4. 站内通知：写入 `alert_unread` 表，提供 API 轮询

## 已实现

### `backend/alerter.py`

- `AlertDeduplicator` — 去重，每天每 ticker 最多一条
- `AlertUnreadStore` — 未读告警存储
- `StockAlerter` — 定时检查 + 触发告警
- `check_stock_alert()` — 单股检查逻辑
- `format_alert_message()` — 消息格式化

### `backend/database.py`

- 新增 `alert_history` 和 `alert_unread` 表

### `backend/main.py`

- `GET /api/alerts/` — 获取所有未读告警
- `GET /api/alerts/count` — 未读数量
- `POST /api/alerts/clear` — 清除所有告警
- `POST /api/alerts/check` — 手动触发检查

### 定时任务

`StockAlerter` 在 FastAPI lifespan 中启动（`alerter.start()`），后台线程每 `ALERT_CHECK_INTERVAL` 秒（默认 300s）检查一次。

## 验收条件

- [x] `python3 backend/test_data_fetcher.py` — ALL TESTS PASSED
- [x] 去重逻辑测试通过（同一 ticker 第二次不触发）
- [x] `check_stock_alert()` 逻辑正确（threshold < 0 时才触发）
- [x] API 端点已注册到 FastAPI

## Comments

- 2026-08-14（agent 收尾）：验收全部完成，`Status: done`（此前状态行停留在 ready-for-agent 属记录债务，本次清理）。