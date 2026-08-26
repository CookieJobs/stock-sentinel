# Risk Alert Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn persistent 52-week drawdown notifications into opt-in, one-time breach alerts that rearm after recovery.

**Architecture:** Keep the existing SQLite and threading design. Add alert configuration to `stocks` and a per-ticker state table; the alerter evaluates an explicit state transition before creating existing unread/history records. Dashboard config remains in the existing page and talks to the existing stock endpoints.

**Tech Stack:** Python/FastAPI/sqlite3, React 19, Tailwind v4, pytest, npm.

**Spec:** `.scratch/risk-alert-refinement/PRD.md`

## Global Constraints

- Do not delete or rebuild user database tables; migrations must be additive and preserve legacy records.
- Do not add dependencies or external push services.
- A drawdown notification is a risk-attention signal, never a trade instruction.

---

### Task 1: Establish backend alert behavior with tests

**Files:**
- Create: `backend/test_alerter.py`
- Modify: `backend/database.py`
- Modify: `backend/alerter.py`

**Interfaces:**
- Produces `StockAlerter._check_all()` behavior: a newly breached enabled stock creates one unread record; an already-breached stock creates none.
- Produces a positive public `threshold` and boolean `alert_enabled` configuration.

- [x] **Step 1: Write failing tests** for a positive 15% enabled threshold crossing at -16%, repeated checks, recovery at -12%, and anomalous -99% data.
- [x] **Step 2: Run `python backend/test_alerter.py`** and confirm the tests fail because the current implementation rejects positive thresholds and lacks alert state.
- [x] **Step 3: Add additive SQLite schema and state-machine implementation** with `alert_enabled`, `alert_state`, historical snapshots, freshness and anomaly guards.
- [x] **Step 4: Run `python backend/test_alerter.py`** and confirm all new alert cases pass.
- [ ] **Step 5: Commit backend implementation and tests** with a Chinese `feat(alert):` message.

### Task 2: Surface explicit configuration and alert context

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/monitor.py`
- Modify: `frontend/src/pages/Dashboard.jsx`

**Interfaces:**
- Consumes `StockResponse.alert_enabled`, positive `StockResponse.threshold`, and alert history snapshots.
- Produces an explicit Dashboard setting for 52-week drawdown attention alerts.

- [x] **Step 1: Update the Dashboard to submit an `alert_enabled` boolean and positive threshold.**
- [x] **Step 2: Display `未启用` for disabled stocks and breach snapshot information in alert views.**
- [x] **Step 3: Run `cd frontend && npm run lint`**, fixing only reported errors.
- [x] **Step 4: Run `cd frontend && npm run build`** to regenerate `backend/static/`.
- [ ] **Step 5: Commit UI and generated assets** with a Chinese `feat(alert):` message.

### Task 3: Verify and record the release

**Files:**
- Modify: `.scratch/risk-alert-refinement/PRD.md`
- Modify: `.scratch/risk-alert-refinement/issues/01-alert-backend-state.md`
- Modify: `.scratch/risk-alert-refinement/issues/02-alert-dashboard-config.md`
- Modify: `CHANGELOG.md`

- [x] **Step 1: Run `python backend/test_data_fetcher.py`.**
- [x] **Step 2: Run `python -m pytest backend/tests/ -q`.** The sandbox blocks the Tushare tests because the library writes `/Users/liujin/tk.csv`; all other quant tests pass (229 passed).
- [x] **Step 3: Re-run alert tests and frontend lint/build.**
- [x] **Step 4: Inspect `git diff --check` and `git status --short`.**
- [x] **Step 5: Mark PRD/issues done and record exact verification results in the changelog.**
