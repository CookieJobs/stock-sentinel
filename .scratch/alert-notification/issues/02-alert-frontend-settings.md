# Issue 02: 前端告警弹窗内容

Status: done

## 描述

在告警弹窗中展示未读告警列表，支持：
1. 打开弹窗时从 `GET /api/alerts/` 获取告警列表
2. 每条告警显示：股票代码、名称、回撤、阈值、触发时间
3. 清除所有告警按钮

## 已实现

### `Dashboard.jsx`

- `fetchAlertList()` — 获取 `GET /api/alerts/` 列表
- `alerts` state — 告警列表
- 打开弹窗时调用 `fetchAlertList()`
- 告警卡片渲染（ticker、名称、回撤、阈值、现价、触发时间）

### 告警卡片 UI

- 每条告警卡片显示：ticker、名称、回撤（红色）、阈值（黄色）、现价、触发时间
- 打开弹窗时获取列表，清除后弹窗下次打开时重新获取

## 验收条件

- [x] `npm run build` — 编译成功
- [x] ESLint — 无错误
- [x] 弹窗打开时获取告警列表
- [x] 清除按钮调用 `POST /api/alerts/clear` 并重置本地 state

## Comments

- 2026-08-14（agent 收尾）：验收全部完成，`Status: done`（此前状态行停留在 ready-for-agent 属记录债务，本次清理）。