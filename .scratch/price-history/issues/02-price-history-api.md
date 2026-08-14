# Issue 02: 历史行情查询 API

Status: ready-for-agent

## 描述

提供 `GET /api/history/{ticker}?days=30` 查询单只股票的历史价格/回撤序列，供前端 sparkline 与后续简报图表使用：
1. `main.py` 注册端点（必须在静态托管 catch-all 之前）
2. 返回 `{"ticker", "market", "days", "points": [{"captured_at", "current_price", "change_pct", "drawdown", "week52_high"}, ...]}`，按时间升序
3. 无数据返回空 `points`（200），不 404；`days` 有上限（默认 30，最大 90）

## 验收条件

- [ ] 有数据时返回正确的序列结构与升序排列
- [ ] 无数据时返回空 `points` 且状态码 200
- [ ] `days` 参数生效且超上限被截断
- [ ] `python3 backend/test_price_history.py` 的 API 冒烟用例通过

## Blocked by

- `01-price-history-backend`（需要表与落库逻辑）
