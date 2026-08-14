# Changelog

AI 维护者每次收工时按「收工仪式」（AGENTS.md §6）在此追加条目。

## 2025-08-14 — 基础设施：AI 主导模式起步

- 新增 `AGENTS.md`：AI 维护者操作手册（开工仪式 / 工作循环 / 升级规则 / 收工仪式），
  由 DSH `dsh-agent-instructions` 自动注入每次会话。
- 新增 DSH agent preset `stock-sentinel`：AI 维护者 persona（模式 B：AI 自主干，人看结果）。
- 说明：本条目由人工主导的转换会话记录，作为 CHANGELOG 格式的样例。

## 2026-08-14 — 每日简报（Daily Briefing）

- 新功能：每日定时生成中文简报，聚合监控组合状态（市场分布 / 回撤 Top / 超阈值清单 / 今日异动 / 昨今对比），
  支持 LLM 生成（OpenAI 兼容接口，`.env` 配置 `LLM_API_KEY` 等）与无 Key 模板兜底。
- 新增 `backend/briefing.py`：`BriefingGenerator`（快照采集 → 上下文组装 → LLM/模板生成 → 落库）+ `BriefingScheduler`（daemon 线程，默认北京时间 08:30 触发，每天一条）。
- 数据库新增 `stock_snapshots`（每日快照，供对比）与 `briefings`（简报记录，每天一条 REPLACE）两张表。
- 新 API：`GET /api/briefings/`、`GET /api/briefings/latest`、`GET /api/briefings/{id}`、`POST /api/briefings/generate`。
- 前端：Dashboard 新增「📰 简报」入口 + `frontend/src/components/BriefingModal.jsx`（轻量 markdown 渲染、历史切换、手动生成）。
- 修复：`/api/alerts/*` 被 catch-all 静态路由遮蔽导致一直返回 HTML 的既有 bug（Alert API 移至静态托管之前）。
- 测试：新增 `backend/test_briefing.py`（5/5 通过，临时 DB 隔离）。
- 验证：模板简报已对真实库生成成功（mode=template）；前端 build 通过。
- 未决：`backend/test_data_fetcher.py` 的 demo 断言因东财 API 可达而过时（既有问题，非本次引入）；
  `data_fetcher.py`/`monitor.py` 的未提交改动（直连/日志）未纳入本次提交。
