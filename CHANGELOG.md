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

## 2026-08-14 — 历史行情落库与回撤趋势（Price History）

- 新功能：每次刷新拿到真实行情时写入 `price_history`（15 分钟时间桶幂等，demo 回退不落库，
  保留 90 天可配 `PRICE_HISTORY_RETENTION_DAYS`），Dashboard 新增「趋势」列展示近 30 天回撤 sparkline（纯 SVG，无新依赖）。
- 数据库新增 `price_history` 表（`UNIQUE(ticker, bucket)` + ticker 索引）。
- 新 API：`GET /api/history/{ticker}?days=30`（无数据返回 200 + 空数组，`days` 上限 90）。
- 前端：新增 `frontend/src/components/Sparkline.jsx`；Dashboard 首次加载与全量刷新后拉取历史。
- 修复：`backend/test_data_fetcher.py` 的 demo 断言改为确定性 mock（屏蔽真实 API 验证回退路径），东财可达时不再误红。
- 修复：前端基线遗留的 3 处 `react-hooks/preserve-manual-memoization` lint 错误（三个 fetch* 回调补 setter deps）。
- 清理：issue tracker 过时状态——`alert-notification` 01/02/03 与 `daily-briefing` SPEC 标 `done`；
  triage 词汇表新增 `done` 标签（`docs/agents/triage-labels.md`）。
- 测试：新增 `backend/test_price_history.py`（6/6 通过，临时 DB 隔离）；`test_data_fetcher.py` 与 `test_briefing.py` 全量回归通过；前端 lint + build 通过。
- 提交：`fix`(test_data_fetcher) / `chore`(tracker 清理) / `feat`(历史行情后端+API) / `feat`(前端 sparkline) 共 4 笔，小步分离。
- 未决（需人看）：`backend/data_fetcher.py`、`backend/monitor.py` 的未提交改动仍保持原样未纳入提交（其中东财 URL https→http 降级属安全隐患，建议人工确认）；
  历史行情需真实 API 运行一段时间才有趋势数据，sparkline 初期多为"暂无趋势"占位。
