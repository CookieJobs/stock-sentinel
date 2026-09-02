# Issue 03: 大跌新闻归因（附在简报/告警里）

Status: ready-for-human

## 描述

当某只股票单日跌幅超过阈值时，自动抓取当天相关新闻/公告，用 LLM 总结"为什么跌"，
附在每日简报或告警中推送。

## 依赖

- 需要新增新闻数据源（抓取或第三方 API），涉及外部服务，按 `AGENTS.md`“必须升级给用户的边界”需人工确认
- 简报模块的 LLM 通道已就绪（`briefing.py`），可直接复用

## 数据源评估（2026-08-19，agent）

- ✅ **东财 search-api-web（个股资讯搜索）**：`https://search-api-web.eastmoney.com/search/jsonp`，
  按股票名关键词搜新闻（含标题/日期/来源），本机实测 200 可达、无 key、无成本。
  与东财 push2 行情接口无关（不同域名，不受其风控影响）。
- ✅ 新浪 roll 新闻接口亦可达（通用资讯流，非个股级）。
- 结论：**数据源可用且免费**；此 issue 仍保持 `ready-for-human` 是因为实现需要
  `LLM_API_KEY` 才有效果（无 key 只能附标题列表、无法"总结原因"），且属于新外部 API 接入。
- 用户确认 LLM key + 批准后可实施：`news_service` 拉新闻 → LLM 摘要 → 简报/告警附归因。
