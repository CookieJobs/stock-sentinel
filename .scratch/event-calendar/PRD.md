# PRD: 事件日历（Event Calendar）

Status: done
Owner: agent
Version: 1.0
Date: 2026-08-19

## 概述

按日期展示 A 股的**分红送转 / 限售解禁**事件，帮助用户提前关注除权除息与解禁抛压。

## 实现

- 数据源：Tushare `dividend`（按除权日 ex_date）+ `share_float`（按解禁日 float_date），
  免费档限流时退化为公告日宽窗口 + 客户端过滤。
- 后端：`quant_events` 表；`quant_engine/events_service.py`（refresh/list）；
  API `GET /api/quant/events`、`POST /api/quant/events/refresh`。
- 前端：`/events` 页面（日期区间 + 类型筛选 + 拉取按钮，按日期分组）。
- 测试：`test_events_service.py` 2/2（mock Tushare 响应）。

## Todo

- [x] 后端表 + 服务 + API（commit b0e151c）
- [x] 前端页面 + 路由（commit 73d696d）

## 后续

- 财报披露计划（disclosure_date）与业绩预告（forecast）需要更高 Tushare 积分，当前 token 无权限，已预留扩展点。
