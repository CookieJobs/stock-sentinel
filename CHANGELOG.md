# Changelog

AI 维护者每次收工时按「收工仪式」（AGENTS.md §6）在此追加条目。

## 2026-08-20 — 东财延时因子源：真实因子数据全量落地（5552 只）

- 调研发现 `push2delay.eastmoney.com`（延时 15 分钟）与 push2 同构但不被风控，
  clist 提供全 A 股 PE(动)/PE-TTM/PB/ROE/换手率/市值/行业。
- 新增 `EastMoneyDelayFactorSource` 接入降级链：Tushare → **东财延时** → BaoStock → AkShare → Mock。
- 修复两处：
  1. `refresh_universe` 只认「含因子列的 df」为源成功——Tushare 限流回退的"空壳 universe"
     不再阻断降级链（此前导致东财延时源永远轮不到）；
  2. clist 分页：单页上限 100 + 后段页偶发超时 → 每页重试 3 次。
- **真实数据验证**：`refresh_universe()` → 21205 因子行；turnover_rate 5552 只完整、
  pe_ttm/pb/roe 5215+ 只；抽查茅台 PE 19.54 / PB 6.33 / ROE 16.75、平安银行 PE 5.09 / PB 0.47。
- 清理：删除失败刷新遗留的 5547 行全空 daily_metrics 占位（daily_metrics 现为 5552 行真实数据）。
- 测试：`test_eastmoney_delay_source` 2/2（新增）+ 既有 11 个新测试全过（13 passed）。
- 提交：`a0ab7e1`…`d14b132` 之后新增本功能提交（见 git log）。
- 未决：财务深数据（毛利率/营收增速等）仍需 Tushare 积分升级或 BaoStock 网络恢复。

## 2026-08-19 — Tushare 真数据接入 + 事件日历 + 策略模板 + 模拟交易

- **Tushare 接入**（用户提供 token）：`TUSHARE_TOKEN` 已写入 `backend/.env`（gitignored，不入库）。
  因子管线新增**双级缓存**（`ts_universe_cache` / `ts_daily_cache`）——免费档 `stock_basic`/`daily_basic`
  限 1 次/小时，首次成功后落库、限流自动回退，避免刷新掉进 Mock 假数据。
  ⚠️ 实测发现该档位完整限制为 **1次/分钟 + 1次/小时 + 5次/天**（失败的调用同样计入窗口）；
  当日配额耗尽后须等北京时间次日 0 点重置。建议升级 200 积分（免费实名）解除瓶颈。
- **事件日历**：Tushare 分红送转（除权日）+ 限售解禁（解禁日）→ `quant_events` 表；
  API `GET /api/quant/events` + `POST /refresh`；前端 `/events` 页（区间 + 类型筛选）。
- **策略模板**：4 个预配置回测模板（低估值红利 / 双均线趋势 / 动量优选 / 等权一篮子），
  回测页一键套用；API `GET /api/quant/backtest/templates`。
- **模拟交易 Paper Trading**：真实行情成交的模拟组合（买卖/现金校验/实现盈亏/净值重估，
  demo 假数据拒绝成交）；`/api/quant/paper` CRUD + trade + mark；前端 `/paper` 页。
- 测试：`test_factor_source` 3/3、`test_events_service` 2/2、`test_strategy_templates` 3/3、
  `test_paper_service` 3/3 全过；前端 lint + build 通过（产物同步）。
- 提交：`0b77b79`(因子缓存) / `b0e151c`+`73d696d`(事件日历) / `89b1b8c`(策略模板) / `bd45b1a`(模拟交易)。
- 未决（需人看）：
  1. Tushare 积分档偏低——`stock_basic`/`daily_basic` 限 1 次/小时；`fina_indicator`/`income`/
     `disclosure_date`/`forecast` 无权限（成长/质量因子、财报披露、业绩预告暂缺，升级积分可解锁）。
  2. `LLM_API_KEY` 未配置——每日简报走模板模式；新闻归因（issue 03）依赖 LLM key。
  3. 真实因子刷新已安排后台验证（配额重置后自动跑，结果待确认）。

## 2026-08-19 — CN/HK 行情多源降级（东财→腾讯）

- 背景：东财 `push2/push2his` 实时行情接口被服务端秒断（见 `.scratch/eastmoney-proxy/PRD.md`），
  行情长期回退 demo 假数据。
- 新功能：`data_fetcher.py` 给 CN/HK 加腾讯行情源作降级——东财失败自动切腾讯
  （`qt.gtimg.cn` 实时报价 GBK 解析 + `web.ifzq.gtimg.cn` 日 K 320 根算 52 周高低点），
  都失败才回退 demo。`source` 字段区分 eastmoney/tencent/demo。
- 修正：实现中曾误用腾讯周 K（会算出约 6 年高低点），改为日 K 对齐东财 ~1.2 年窗口。
- 效果：实测 600519/000001/00700/01810 均 `source=tencent` 拿到真实行情；不再依赖 Clash 对
  东财域名的规则，也基本免疫 push2 风控。
- 测试：`test_data_fetcher.py` ALL PASSED（新增 `_tencent_secid` 纯函数 + 东财失败降级腾讯用例），
  `test_briefing` 6/6、`test_price_history` 6/6。
- 提交：`323215d`(feat) + `aac1f90`(docs 东财 issue 更新)。

## 2026-08-18 — 清理 + 简报趋势图 + 东财连通性根因

- **A 数据清理**：备份 `data/sentinel.db`（`.bak` 已加 `.gitignore`）后，清空量化测试写入真实库的残留
  —— `portfolios` 64 / `portfolio_holdings` 142 / `factor_values` 23118 / `daily_metrics` 9396（全是
  pytest 的 Mock 因子刷新与组合 CRUD 产物，无真实使用痕迹），VACUUM 后库从 5.12MB 缩到 929KB；
  v0.2.0 真实数据（stocks/alerts/briefings/price_history/snapshots）原样保留。
- **B 简报内嵌回撤趋势图**（`.scratch/briefing-trend/`）：后端 `BriefingGenerator._load_trends` 读
  `price_history` 近 30 天回撤序列写入 `briefings.stats.trends`（不进 LLM 上下文省 token，以简报日期为
  窗口基准）；前端 `BriefingModal` 复用 `Sparkline` 渲染「📉 回撤趋势」小节（恶化标红/改善标绿，无数据不出现）。
- **C 东财连通性根因**（`.scratch/eastmoney-proxy/PRD.md`，ready-for-human）：本机 Clash Party（mihomo）
  TUN/fake-IP 模式把 `push2.eastmoney.com`/`push2his` 解析到 198.18.0.x 假 IP，代理路由规则损坏导致
  https 重置/http 502；`data_fetcher.py` 的 http 降级是治标 workaround。修复方向：Clash 加
  `DOMAIN-SUFFIX,eastmoney.com,DIRECT` 规则，修好后 URL 可回 https。
- 提交：`a0ab7e1`(fix 数据源遗留改动入库) / `dee9fa7`+`291d943`(feat 简报趋势图) / `bafee18`+`e1718e8`(chore/docs)。
- 验证：`test_briefing.py` 6/6（含新增趋势用例）、`test_price_history.py` 6/6、`test_data_fetcher.py` ALL PASSED；
  pytest 137 passed；前端 lint + build 通过。
- 未决：并行会话的 `backend/tests/quant_engine/conftest.py`（临时 DB 隔离）+ `test_api.py`（test_db_isolation）
  尚未合入（非本 session 产物，未动）；Clash 东财规则需人工改（见 C）；东财 http 安全债待规则修好后回 https。

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
