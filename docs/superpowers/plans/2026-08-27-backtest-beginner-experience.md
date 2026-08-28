# 回测新手引导与名称选股 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/backtest` understandable for first-time investors while retaining existing professional controls.

**Architecture:** Keep the FastAPI contract unchanged. Add a small pure frontend module for mode defaults, selection validation and payload construction; `Backtest.jsx` consumes it while managing search and form state with the existing `search.stocks` and `backtest` API clients.

**Tech Stack:** React 19, Vite, Tailwind v4, Node built-in test runner, existing FastAPI APIs.

**Spec:** `docs/superpowers/specs/2026-08-27-backtest-beginner-experience-design.md`

## Global Constraints

- Reuse `GET /api/quant/search`; do not add a backend endpoint or dependency.
- Preserve all existing backtest request fields and strategy engine values.
- Use Chinese intent-first copy, visible labels, keyboard-accessible controls, and no color-only feedback.
- Keep a single selected market per run because the backend accepts one `market` value.

---

### Task 1: Testable Backtest Flow Rules

**Files:**

- Create: `frontend/src/lib/backtest-flow.js`
- Create: `frontend/src/lib/backtest-flow.test.js`

**Interfaces:**

- Produces: `MODE_DEFAULTS`, `addStock`, `validateSelection`, `buildRunPayload`.
- Consumes: selected stock objects `{ticker, name, market}` and the current form object.

- [x] **Step 1: Write the failing test**

Create tests for adding a stock, rejecting a one-stock portfolio, rejecting mixed markets, and converting selected stocks into the API payload.

- [x] **Step 2: Run test to verify it fails**

Run `node --test frontend/src/lib/backtest-flow.test.js`. It must fail because the module does not exist.

- [x] **Step 3: Write minimal implementation**

Export the four named helpers. Do not place React state or network requests in this module.

- [x] **Step 4: Run test to verify it passes**

Run `node --test frontend/src/lib/backtest-flow.test.js`. All tests must pass.

- [x] **Step 5: Commit**

Commit the helper and its test as `feat(ui): 增加回测新手流程规则`.

### Task 2: Intent-first Backtest Page

**Files:**

- Modify: `frontend/src/pages/Backtest.jsx`
- Modify: `frontend/src/lib/backtest-flow.js`
- Test: `frontend/src/lib/backtest-flow.test.js`

**Interfaces:**

- Consumes: `MODE_DEFAULTS`, `addStock`, `validateSelection`, `buildRunPayload`, and `search.stocks`.
- Produces: selected-stock UI and the unchanged `backtest.run` payload.

- [x] **Step 1: Write the failing test**

Add the payload test for a selected Chinese-named stock and market `CN`.

- [x] **Step 2: Run test to verify it fails**

Run the Node test and confirm the missing payload helper is the reason.

- [x] **Step 3: Write minimal implementation**

Replace the code text field with search, selected-stock tags, two mode controls, a one-year date range, a readable run summary, and `<details>` containing the existing expert inputs.

- [x] **Step 4: Run test to verify it passes**

Run the Node test after the page uses the helper.

- [x] **Step 5: Commit**

Commit the page and test changes as `feat(ui): 回测页支持名称选股与渐进设置`.

### Task 3: Verify and Record

**Files:**

- Modify: `.scratch/backtest-beginner-experience/PRD.md`
- Modify: `.scratch/backtest-beginner-experience/issues/01-beginner-backtest-flow.md`
- Modify: `CHANGELOG.md`
- Generated: `backend/static/`

- [x] **Step 1: Run focused checks**

Run `node --test frontend/src/lib/backtest-flow.test.js`, `npm --prefix frontend run lint`, and `npm --prefix frontend run build`.

- [x] **Step 2: Run browser verification**

Open `/backtest`; verify Chinese-name search, direct code entry, tag removal, mode validation, market restriction, and advanced settings.

- [x] **Step 3: Record outcome**

Mark the PRD and issue `done`; add the date, changes, checks and the Tushare sandbox baseline limitation to `CHANGELOG.md`.

- [x] **Step 4: Commit**

Commit the documentation and generated static assets as `docs: 记录回测新手流程交付`.
