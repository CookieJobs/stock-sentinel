# Changelog

AI 维护者每次收工时按「收工仪式」（AGENTS.md §6）在此追加条目。

## 2026-08-15 — 与 GitHub 合并：量化分析平台（v1.0）入库

- 同步远端 20 个提交：合并 `origin/main`（本地 +10 提交、远端 +20 提交，分叉点 2026-05-16）。
  解决 4 处冲突：`AGENTS.md`（本地操作手册 × 远端协作指南合并）、`CLAUDE.md`（Backend 架构段合并，
  保留量化分层 + 本地 briefing/price_history 描述）、`backend/main.py`（保留双方 import）、
  `backend/static/index.html`（取远端，随后重新 build 覆盖）。
- 入库内容：`backend/quant_engine/` 全套（M0-M6：K 线 / 指标 / 因子选股 / 回测 / 组合 / 风险，
  数据源 AkShare / BaoStock / 东财 / Finnhub）、前端 6 页面 + react-router、
  `backend/tests/quant_engine/`（137 测试）、USER_GUIDE / README / quant-roadmap / ADR 文档。
- 修复 `fix(quant)`：BaoStock login 无超时——其 `send_msg` 是 `while: recv` 循环，
  网络代理断连（recv 返回 b''）时无限空转，因子刷新/测试挂 68s+；改为 daemon 线程 + 10s 超时，
  fallback 链 12.5s 内完成。验证：pytest 137/137 通过、`test_data_fetcher.py` 全过、
  前端 lint 0 警告 + build 通过。
- 未决：工作区 `data_fetcher.py`/`monitor.py` 未提交改动（日志/HTTP 直连/demo 防覆盖）未纳入提交；
  本机 akshare 因 openpyxl 版本（3.0.10 < 3.1.0）降级不可用，因子数据走 Mock fallback；
  尚未推送合并结果到 GitHub（需用户确认）。

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
