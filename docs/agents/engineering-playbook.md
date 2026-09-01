# StockSentinel 工程操作手册

## 适用范围与读取时机

本手册记录会随工程演进而变化的实现、验证与交接约定。开展代码、测试、构建、Git 或数据操作前阅读相关章节；产品判断、权限边界和长期原则以根目录 [CONSTITUTION.md](../../CONSTITUTION.md) 为准，架构与 API 细节以 [CLAUDE.md](../../CLAUDE.md) 为准。

开始一个会话时，先执行 `git status` 和 `git log --oneline -8`，确认基线及未提交改动；他人的未提交改动不得擅自提交。随后查看 `.scratch/` 内 issue 的 `Status:`、相关 PRD 的 `## Todo` 和 `CHANGELOG.md` 最近记录，再向用户简要说明现状与本次计划。

挑选工作时优先处理 `ready-for-agent` 的完整事项；没有待办时，先为新功能建立 PRD 和可执行事项。事项格式、状态与标签以 [issue tracker](issue-tracker.md) 和 [triage labels](triage-labels.md) 为准。实现中遵循既有模式：后端使用无 ORM 的 `sqlite3` 与 `threading`，前端使用 React 19、Tailwind v4 与 `react-router`。

完成工作后，更新相关 issue 的 `Status:` 与 `## Comments`、PRD 的 `## Todo`，并在 `CHANGELOG.md` 记录日期、改动、验证结果与未决事项。汇报应说明已完成内容、验证结果、需要关注的决策或行为变化，以及下一步建议；不得夸大完成度。

## 第一次接手

- 阅读 `CONTEXT.md`、[CLAUDE.md 的 Architecture](../../CLAUDE.md) 与 [量化路线图](../quant-roadmap.md)，再读 `CHANGELOG.md` 最近记录。
- 运行 `./start.sh`，通过 `http://localhost:5173` 浏览 6 个页面；开发时只访问该地址，由 Vite 将 `/api` 转发到 `:8000`。
- 运行 `python -m pytest backend/tests/ -q`，确认当前完整测试集通过。
- 扫描 `.scratch/`，按 [issue tracker](issue-tracker.md) 选择下一项工作。

远端资料所述的 `.claude/PROJECT_HISTORY.md` 和 `.claude/TODO.md` 可能受 `.gitignore` 屏蔽而不存在；缺失时以仓库内的 `CHANGELOG.md`、PRD 和上述文档为准。

## 开发与运行命令

首次准备环境的方式及服务架构见 [CLAUDE.md](../../CLAUDE.md)。日常命令如下：

```bash
# 后端 API（:8000）
python backend/main.py

# 后端测试与数据抓取冒烟测试
python -m pytest backend/tests/ -q
python backend/test_data_fetcher.py

# 前端开发、检查与生产构建（:5173）
cd frontend && npm run dev
cd frontend && npm run lint
cd frontend && npm run build

# 同时启动前后端
./start.sh
```

## Commit 前质量门

提交前必须依次通过以下完整质量门；任何一项失败都不得提交。若影响范围不确定，额外运行相关测试。

```bash
python -m pytest backend/tests/ -q
python backend/test_data_fetcher.py
cd frontend && npm run lint && npm run build
```

前端有改动时，`npm run build` 生成的 `backend/static/` 构建产物必须随源码一并提交。当前完整测试集、冒烟测试、lint 或 build 的既有警告可记录为基线警告，但不得把新增失败当作通过。

## 量化引擎代码规范

- 指标和因子优先写成纯函数：`pd.Series → pd.Series`；函数内不得 `print` 或记录调试日志。
- 用 `dataclass` 承载状态，例如 `Trade`、`BacktestResult`、`TradeRecord`；用 `pd.DataFrame` 承载批量回测数据。
- 业务校验错误使用 `ValueError`，API 层错误使用 `HTTPException`。
- 调用外部 API 必须用 `try/except` 保护，因为数据源不稳定；失败时按既有降级约定处理，不伪造成功结果。

## 测试规范

- 每个新指标、因子或函数必须有单元测试；每个 API endpoint 必须有 `TestClient` 集成测试。
- 覆盖 happy path、边界条件和错误路径。
- 修复 bug 时先写会失败的回归测试重现 bug，再修改实现，并在提交前运行完整质量门。
- 不得删除现有测试，除非已确认其确实过时且替代覆盖仍在。

## Git、worktree 与构建产物

- 保持小步提交：一次提交一件事，单个 commit 不超过约 500 行改动；测试通过后才可提交。
- commit message 使用中文并采用 `feat:`、`fix:`、`docs:` 或 `chore:` 前缀；需要时带 scope，例如 `feat(quant):`。消息应写清原因、改动和测试结果，禁止 `update` 等空泛消息。
- 大型功能建议在隔离 worktree 中完成，例如 `git worktree add .worktrees/<feat> -b feature/<x> origin/main`，使主 checkout 保持可回退；日常小改动可直接在当前 checkout 完成。
- 进度检查使用 `git log --oneline -10` 和 `git worktree list`。不要提交 `__pycache__/`、`node_modules/`、`data/sentinel.db`、`.env`、`.worktrees/` 或 `.claude/`。
- 构建产物仅在前端源码变更并完成 `npm run build` 后同步提交；不得只改前端源码而遗漏 `backend/static/`。

## 禁止事项与数据安全

以下操作必须停下并用一句话向用户说明后等待指示：

- 删除、迁移或清空 `data/sentinel.db`，以及任何不可逆操作（包括破坏性数据库迁移）。
- 更换数据库或框架、重写整个模块、引入新的基础设施，或进行删除文件、大规模重构、重命名核心模块等架构级改动。
- 添加付费或重型依赖，或接入涉及费用、密钥或长期成本的外部服务/API。
- 修改 `.env`、API key、凭据或其他敏感配置。
- 向远端 `main` 或 `master` 推送。

新功能，以及会改变用户可见行为、数据格式或告警触发语义的设计决策，须先在 `.scratch/<feature>/PRD.md` 建立 PRD 并拆成事项；随后可按 `ready-for-agent` 继续实施。对行为变化、新增外部 API 调用、数据格式变化、技术债或重要设计取舍，应主动告知用户；技术债应记录为事项。

## 常见任务模板

### 新指标

1. 在 `backend/quant_engine/indicators.py` 添加纯函数（`pd.Series → pd.Series`）。
2. 在 `INDICATORS` 注册表登记 `fn`、`params`、`inputs`。
3. 振荡器指标需要时加入 `OSCILLATOR_INDICATORS`。
4. 在 `backend/tests/quant_engine/test_indicators.py` 添加测试，执行相关 pytest 与完整质量门后提交。

### 新数据源

1. 在 `backend/quant_engine/data_source/` 新建实现并继承 `DataSourceBase`。
2. `get_kline(ticker, market, period, start, end, adj)` 返回列为 `trade_date`、`open`、`high`、`low`、`close`、`volume`、`amount` 的 `pd.DataFrame`。
3. 在 `__init__.py` 的 `SOURCES` 列表按优先级注册，并用 `try/except` 保持外部数据失败可控。
4. 添加测试，执行质量门后提交。

### 修复 bug

1. 先添加失败的测试，稳定重现 bug。
2. 修改最小必要实现，确认回归测试通过。
3. 运行完整质量门，提交消息说明 bug 所在、修复方式与测试覆盖。

## 故障排查与长会话交接

卡住时先阅读 `CHANGELOG.md` 和 `docs/adr/`，了解已有决策与踩坑记录；关键决策使用 ADR 记录，并标明被推翻的 ADR。再运行相关测试以定位问题；需要判断方向或范围时向用户提问，不自行决定重大方向。

领域术语以 [Domain](domain.md) 为准；缺失术语通过 `grill-with-docs` 沉淀，而不是自行定义。长会话或换手前使用 `handoff` skill 在 `.scratch/handoff/` 生成交接文档，写明当前状态、已验证内容、未决事项和后续命令。
