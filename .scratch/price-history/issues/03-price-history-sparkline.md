# Issue 03: 前端个股回撤趋势 sparkline

Status: ready-for-agent

## 描述

Dashboard 股票列表的每行显示该股最近 30 天回撤走势的小图（纯 SVG `<polyline>`，不引入图表库）：
1. 行内渲染 sparkline：X 轴为时间点，Y 轴为 `drawdown`（负数在下、0 在上）
2. 数据来自 `GET /api/history/{ticker}?days=30`；无数据时显示"暂无趋势"占位
3. 悬浮/标题提示显示首末回撤值；颜色按当前 `market_status`（alert 红 / warning 黄 / normal 绿）
4. 不阻塞主列表渲染：拉取失败静默降级为占位

## 验收条件

- [ ] `cd frontend && npm run lint` 无错误
- [ ] `cd frontend && npm run build` 通过，产物同步到 `backend/static/` 并提交
- [ ] 有数据行显示 sparkline，无数据行显示占位，均不报错

## Blocked by

- `02-price-history-api`（前端数据来源）
