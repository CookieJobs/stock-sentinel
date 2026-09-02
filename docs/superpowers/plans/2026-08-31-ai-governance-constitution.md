# StockSentinel AI Governance Constitution Implementation Plan

Status: implemented

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Completed steps use checked checkbox (`- [x]`) syntax for tracking.

**Goal:** Establish a three-layer AI governance system that makes StockSentinel's product principles mandatory while keeping the automatically loaded agent instructions concise and the engineering rules complete.

**Architecture:** `CONSTITUTION.md` becomes the stable source of truth for product values and human/AI authority; root `AGENTS.md` becomes the short loading and workflow contract; `docs/agents/engineering-playbook.md` becomes the task-loaded source for changing engineering details. `CONTEXT.md` routes new maintainers through those layers, and the design spec plus changelog record the decision and its validation.

**Tech Stack:** Markdown governance documents, Git, shell validation, existing Python/FastAPI and React/Vite project quality gates.

**Spec:** `docs/superpowers/specs/2026-08-31-ai-governance-constitution-design.md`

**Stable audit base:** `2f3b8b6`

**Implementation and audit commits (6):** `e2dc113`, `cbd2ce9`, `bbb2c21`, `297fca7`, `94bff85`, `fd9c721`. This list records the implementation and audit history before the final-review fix commit.

## Implementation record and controller deviations

1. Task 5 used stable base `2f3b8b6` instead of the count-relative `HEAD~4`. The required Task 2 review fix added a commit, so the relative range no longer represented the pre-implementation state.
2. The controller ran the required read-only fresh-agent comprehension check and supplied its output to the Task 5 implementer because SDD implementers could not dispatch subagents; the independent check still completed with exit 0 and did not modify the worktree.
3. Final reporting uses the six actual implementation and audit commits listed above rather than the plan's predicted five; `bbb2c21` is the reviewed Task 2 correction and is part of the delivered history.

After final review, the controller also approved a minimum docs-only scope expansion for single-source engineering policy and valid navigation. It covers the affected architecture/context/domain references, two current daily-briefing issues, this plan, and existing governance records; it excludes `.scratch/stock-logos/` and all runtime, generated, database, dependency, and configuration files. Project-wide worktree and quality-gate policy remains authoritative only in [`docs/agents/engineering-playbook.md`](../../agents/engineering-playbook.md), and indicator functions retain the original prohibition on `print` or any logging.

## Global Constraints

- For this governance implementation, make all changes in the isolated `codex/ai-governance-constitution` worktree; this task-specific isolation does not override the project-wide policy in the engineering playbook. Preserve unrelated stock-logo and visualization work in the main checkout.
- Do not modify application code, generated frontend assets, database files, environment files, dependencies, or `.scratch/stock-logos/`.
- Preserve every existing safety boundary and quality gate from the pre-change `AGENTS.md`; relocate details instead of silently dropping them.
- Keep `CONSTITUTION.md` stable and implementation-agnostic: no release version, fixed test count, current library choice, or command that is likely to become stale.
- Use Chinese for repository governance content and commit messages, matching the existing project style.
- Before every commit, run the complete current repository gate defined in the engineering playbook; do not copy its commands into secondary documents.
- Expected baseline: the Python suite and data-fetcher smoke tests pass; frontend lint and build pass. A NumPy divide-by-zero warning in the existing risk-analysis test and Vite's existing large-chunk warning may remain, but no new failure or warning category may be introduced.

---

### Task 1: Create the project constitution

**Files:**

- Create: `CONSTITUTION.md`
- Reference: `docs/superpowers/specs/2026-08-31-ai-governance-constitution-design.md`
- Reference: `CONTEXT.md`

- [x] **Step 1: Re-read the approved source of truth**

  Read the entire design spec and the current `CONTEXT.md`. Confirm that this task changes governance only and that StockSentinel remains a decision-support product, not an automated investment adviser.

- [x] **Step 2: Write the constitutional preamble and authority statement**

  Create `CONSTITUTION.md` with a short preamble that says:

  - the document governs product planning, implementation, review, and agent behavior;
  - it is read after applicable platform rules and the user's current explicit instruction;
  - a user instruction that conflicts with a constitutional principle must be surfaced before execution;
  - lasting exceptions require an explicit constitutional or ADR update.

- [x] **Step 3: Write the ten required principle sections**

  Use these exact section topics, each with concrete decision rules rather than slogans:

  1. 使命与目标用户
  2. 小白优先
  3. 低注意力设计
  4. 用户体验优先
  5. 真实数据与诚实表达
  6. 量化有效性
  7. 产品取舍
  8. 人与 AI 的权责
  9. 完成与学习
  10. 冲突、例外与修订

  Include the spec's requirements for progressive disclosure, actionable summaries, low-noise alerts, data provenance/freshness/coverage, explicit degradation, future leakage and bias controls, reproducibility, benchmark and cost awareness, irreversible-action escalation, user veto power, and verified user outcomes.

- [x] **Step 4: Check constitution size and stability**

  Run:

  ```bash
  wc -l CONSTITUTION.md
  rg -n '小白|盯盘|用户体验|数据来源|新鲜度|不确定|未来函数|数据泄漏|幸存者偏差|过拟合|交易成本|可复现|基准|不可逆|最终否决|修订' CONSTITUTION.md
  rg -n 'v[0-9]+\.|[0-9]+[+]?[[:space:]]*个?测试|pytest|npm|React|FastAPI|sqlite|Tailwind' CONSTITUTION.md
  ```

  Expected: 80–160 lines; the required concepts are present; the final search returns no matches.

- [x] **Step 5: Review the constitution against novice and low-attention use**

  Read the file once as a first-time investor with a full-time job. Confirm that every core principle can answer a future product tradeoff and that no rule assumes professional quantitative knowledge or daily screen time.

- [x] **Step 6: Run repository gates**

  From the worktree root, run the complete repository gate from the engineering playbook.

  Expected: all four commands pass with only the documented baseline warnings.

- [x] **Step 7: Commit the constitution**

  ```bash
  git add CONSTITUTION.md
  git commit -m "docs: 建立 StockSentinel 项目宪法"
  ```

---

### Task 2: Extract the engineering playbook without losing rules

**Files:**

- Create: `docs/agents/engineering-playbook.md`
- Reference: `AGENTS.md` at the Task 1 commit
- Reference: `CLAUDE.md`
- Reference: `docs/agents/issue-tracker.md`
- Reference: `docs/agents/triage-labels.md`

- [x] **Step 1: Inventory the detailed rules in the existing agent manual**

  Before rewriting `AGENTS.md`, map its detailed rules into the new playbook. The inventory must cover:

  - first-time takeover checklist and local run commands;
  - backend tests, data-fetcher smoke test, frontend lint, and frontend build;
  - quant-engine pure functions, dataclasses, DataFrames, error handling, and external API protection;
  - test expectations for indicators, factors, endpoints, boundaries, errors, and bug-first reproduction;
  - Git status, worktrees, generated static assets, small commits, message style, ignored files, and destructive-action restrictions;
  - new indicator, new data source, and bug-fix templates;
  - troubleshooting, ADRs, domain terminology, handoffs, and progress inspection.

- [x] **Step 2: Create the playbook with task-oriented navigation**

  Write `docs/agents/engineering-playbook.md` with these sections:

  - 适用范围与读取时机
  - 第一次接手
  - 开发与运行命令
  - Commit 前质量门
  - 量化引擎代码规范
  - 测试规范
  - Git、worktree 与构建产物
  - 禁止事项与数据安全
  - 常见任务模板
  - 故障排查与长会话交接

  Preserve the current commands and behavior. Replace fixed test counts with wording such as “当前完整测试集”, and use links for facts already owned by `CLAUDE.md` or the issue-tracker documents.

- [x] **Step 3: Verify rule preservation and avoid duplicate principles**

  Search the engineering playbook for its quality-gate section and the required coding, testing, Git, safety, template, ADR, and handoff topics. Separately confirm that constitutional product principles are not duplicated there.

  Expected: every engineering topic is found; the second search returns no matches because product principles remain authoritative in the constitution.

- [x] **Step 4: Check every referenced file**

  Run:

  ```bash
  for governance_path in CLAUDE.md docs/agents/issue-tracker.md docs/agents/triage-labels.md docs/agents/domain.md docs/quant-roadmap.md; do
    test -f "$governance_path" || exit 1
  done
  ```

  Expected: exit status 0 and no output.

- [x] **Step 5: Run repository gates**

  Run the complete repository gate from the engineering playbook.

  Expected: all four commands pass with only the documented baseline warnings.

- [x] **Step 6: Commit the playbook**

  ```bash
  git add docs/agents/engineering-playbook.md
  git commit -m "docs: 拆分 AI 工程操作手册"
  ```

---

### Task 3: Turn AGENTS.md into the loading and workflow contract

**Files:**

- Modify: `AGENTS.md`
- Reference: `CONSTITUTION.md`
- Reference: `docs/agents/engineering-playbook.md`
- Reference: `docs/superpowers/specs/2026-08-31-ai-governance-constitution-design.md`

- [x] **Step 1: Rewrite the mandatory loading gate at the top**

  In the first section of `AGENTS.md`, require every planning, implementation, and review agent to read `CONSTITUTION.md` completely before taking project action. State that:

  - one read per unchanged session is sufficient;
  - a new independent sub-agent, project switch, or constitutional change requires another read;
  - failure to read the constitution blocks product and implementation decisions;
  - code changes, implementation planning, and code review also require `docs/agents/engineering-playbook.md`.

- [x] **Step 2: Add the project instruction priority**

  Record this repository-level order without claiming precedence over platform safety or tool permissions:

  1. user's current explicit instruction, after surfacing any constitutional conflict;
  2. `CONSTITUTION.md`;
  3. applicable `AGENTS.md` files;
  4. approved PRD, issue, implementation plan, and ADR;
  5. context, architecture, domain, and engineering reference documents;
  6. existing code patterns, investigated when they disagree with documents.

- [x] **Step 3: Preserve the concise operating contract**

  Keep and tighten these sections from the old file:

  - identity, product scope, and Mode B responsibility;
  - startup ritual: Git state, `.scratch/` issue statuses, relevant PRD todo, changelog, one-line user update;
  - work loop: PRD → issue → implementation → verification → commit → records;
  - absolute escalation boundaries and PRD-before-change rules;
  - proactive reporting requirements;
  - completion discipline and fixed closeout report;
  - task-based document map.

  Link to the playbook instead of copying test commands, coding rules, templates, and troubleshooting details.

- [x] **Step 4: Check size and retained authority**

  Run:

  ```bash
  wc -l AGENTS.md
  sed -n '1,40p' AGENTS.md
  rg -n 'CONSTITUTION.md|engineering-playbook.md|git status|\.scratch/|PRD|ready-for-agent|不可逆|sentinel.db|付费|凭据|架构|远端|CHANGELOG|本次做了什么|验证结果|需要人看的|下一步建议' AGENTS.md
  ```

  Confirm separately that task templates, data-structure rules, and concrete gate commands do not appear in `AGENTS.md`.

  Expected: 100–180 lines; the loading gate appears in the first 40 lines; all authority and workflow terms are present; the final search returns no matches because those details moved to the playbook.

- [x] **Step 5: Run repository gates**

  Run the complete repository gate from the engineering playbook.

  Expected: all four commands pass with only the documented baseline warnings.

- [x] **Step 6: Commit the concise agent entry point**

  ```bash
  git add AGENTS.md
  git commit -m "docs: 精简 Agent 入口与执行契约"
  ```

---

### Task 4: Update onboarding and document routing

**Files:**

- Modify: `CONTEXT.md`
- Reference: `CONSTITUTION.md`
- Reference: `AGENTS.md`
- Reference: `docs/agents/engineering-playbook.md`

- [x] **Step 1: Correct the context document's entry points**

  Update `CONTEXT.md` so its opening links only to existing, versioned repository documents instead of ignored local-only history or todo files. Keep `CONTEXT.md` as the 30-second product and architecture snapshot.

- [x] **Step 2: Correct repository facts needed for onboarding**

  Replace the stale absolute root path with `/Users/liujin/Documents/stock-sentinel/`. Do not broadly rewrite historical delivery status or roadmap content in this governance-only change.

- [x] **Step 3: Update the document tree and first-read sequence**

  Add `CONSTITUTION.md`, `AGENTS.md`, and `docs/agents/engineering-playbook.md` to the document map. Change the onboarding order to:

  1. `CONSTITUTION.md`
  2. `CONTEXT.md`
  3. `AGENTS.md` for the operating contract
  4. `CLAUDE.md` and the engineering playbook for code work
  5. current PRD, issues, ADRs, domain docs, and roadmap as required by the task

- [x] **Step 4: Verify routing and remove dead references**

  Run:

  ```bash
  rg -n 'CONSTITUTION.md|AGENTS.md|engineering-playbook.md|/Users/liujin/Documents/stock-sentinel/' CONTEXT.md
  for governance_path in CONSTITUTION.md AGENTS.md CONTEXT.md CLAUDE.md docs/agents/engineering-playbook.md docs/agents/issue-tracker.md docs/agents/triage-labels.md docs/agents/domain.md docs/quant-roadmap.md; do
    test -f "$governance_path" || exit 1
  done
  ```

  Confirm separately that obsolete local-only history/todo paths and the old absolute checkout path no longer appear in `CONTEXT.md`.

  Expected: the new paths are found, dead-path search produces no matches, and every routed file exists.

- [x] **Step 5: Run repository gates**

  Run the complete repository gate from the engineering playbook.

  Expected: all four commands pass with only the documented baseline warnings.

- [x] **Step 6: Commit onboarding changes**

  ```bash
  git add CONTEXT.md
  git commit -m "docs: 更新 AI 维护者接手导航"
  ```

---

### Task 5: Audit the governance system with a fresh agent

**Files:**

- Modify: `docs/superpowers/specs/2026-08-31-ai-governance-constitution-design.md`
- Modify: `CHANGELOG.md`
- Verify: `CONSTITUTION.md`
- Verify: `AGENTS.md`
- Verify: `CONTEXT.md`
- Verify: `docs/agents/engineering-playbook.md`

- [x] **Step 1: Run structural and formatting checks**

  ```bash
  git diff --check 2f3b8b6..HEAD
  for governance_path in CONSTITUTION.md AGENTS.md CONTEXT.md CLAUDE.md docs/agents/engineering-playbook.md docs/agents/issue-tracker.md docs/agents/triage-labels.md docs/agents/domain.md docs/quant-roadmap.md; do
    test -f "$governance_path" || exit 1
  done
  if rg -n 'TBD|TODO|PLACEHOLDER' CONSTITUTION.md AGENTS.md CONTEXT.md docs/agents/engineering-playbook.md; then exit 1; fi
  ```

  Expected: no whitespace errors, missing files, or unresolved placeholders.

- [x] **Step 2: Audit every old AGENTS.md rule against its new owner**

  Compare the pre-refactor file with the new two-file split:

  ```bash
  git show 2f3b8b6:AGENTS.md > /tmp/stock-sentinel-agents-before.md
  git diff --no-index /tmp/stock-sentinel-agents-before.md AGENTS.md || true
  ```

  Review the old file section by section. Confirm that stable product principles live only in `CONSTITUTION.md`, operational entry rules live in `AGENTS.md`, and engineering details live in the playbook. If any safety boundary, quality gate, or useful task template has no owner, restore it before proceeding.

- [x] **Step 3: Run a read-only fresh-agent comprehension check**

  Confirm the local Codex executable exists, then launch a clean read-only check from the worktree:

  ```bash
  command -v codex
  codex exec --ephemeral --sandbox read-only "Follow all repository instructions. Do not change files. Summarize in Chinese: the target user; the three core product principles; data and quantitative-truth requirements; decisions that require human escalation; and the required work cycle. Cite the repository documents that support each part."
  ```

  Expected: the response identifies novice users with little time to watch markets; novice-first, low-attention, and UX-first principles; real/provenanced data plus bias/leakage/cost controls; irreversible data, credentials, paid services, architecture replacement, and real-money actions as escalation boundaries; and the PRD → issue → implementation → verification → commit → record cycle. It must cite `CONSTITUTION.md` and `AGENTS.md` without modifying files.

- [x] **Step 4: Review the fresh-agent answer and correct the source documents**

  If the agent misses or misstates any expected item, improve the responsible governance document and repeat Step 3. Do not coach the verification prompt with wording absent from the repository.

- [x] **Step 5: Record completion and evidence**

  Change the design spec status from `approved` to `implemented`. Append a dated `2026-08-31` entry to `CHANGELOG.md` containing:

  - the new three-layer governance structure;
  - confirmation that runtime behavior and databases were untouched;
  - exact verification results, including baseline-only warnings;
  - the fresh-agent comprehension result;
  - any remaining follow-up, such as future automated documentation lint, explicitly marked as out of scope.

- [x] **Step 6: Run final verification**

  ```bash
  git diff --check
  ```

  Then run the complete repository gate from the engineering playbook.

  Expected: no diff errors; all four project gates pass with only the documented baseline warnings.

- [x] **Step 7: Review the final diff for scope containment**

  ```bash
  git status --short
  git diff --stat 2f3b8b6
  git diff --name-only 2f3b8b6
  ```

  At the original Task 5 audit boundary, changed paths were limited to:

  - `CONSTITUTION.md`
  - `AGENTS.md`
  - `CONTEXT.md`
  - `CHANGELOG.md`
  - `docs/agents/engineering-playbook.md`
  - `docs/superpowers/specs/2026-08-31-ai-governance-constitution-design.md`

  The subsequent final-review fix uses the minimum docs-only expansion recorded above. It adds only the affected architecture, domain, current tracker, implementation-plan, and governance references; no runtime or generated files are permitted.

- [x] **Step 8: Commit the audit record**

  ```bash
  git add CHANGELOG.md docs/superpowers/specs/2026-08-31-ai-governance-constitution-design.md
  git commit -m "docs: 完成 AI 治理分层落地"
  ```

- [x] **Step 9: Prepare the user handoff**

  Report the six actual implementation and audit commits, exact verification results, the fresh-agent comprehension outcome, the isolated worktree path, and any baseline warning or npm audit issue that was not introduced by this work. Ask the user to review the branch diff; do not push or merge without explicit direction.
