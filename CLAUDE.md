# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Operating manual**: `AGENTS.md` at the repo root is the AI-maintainer operating
> manual (session ritual, work loop, escalation policy, closing ritual). Read it
> first; this file is the architecture reference.

## Project overview

StockSentinel is a stock monitoring and alerting system tracking drawdown from 52-week highs across US, CN (A-share), and HK markets. A React frontend displays a dashboard; a Python FastAPI backend handles data fetching, persistence, and alerting.

## Commands

```bash
# 一键启动（推荐）
./start.sh                                # 同时启动前后端 → 访问 http://localhost:5173

# 或分别启动
python backend/main.py                    # Start API server on :8000
cd frontend && npm run dev                # Dev server on :5173, proxies /api → :8000
cd frontend && npm run build              # Builds into backend/static/ for serving
cd frontend && npm run lint               # ESLint
python backend/test_data_fetcher.py       # Run data fetcher smoke tests

# 开发时只访问 http://localhost:5173
# :8000 会重定向到 :5173（DEV_MODE=true），:5173 的 /api 代理到 :8000
```

## Architecture

### Backend (`backend/`)

- **`main.py`** — FastAPI app entry point. Lifespan handler starts `StockMonitor` (auto-refresh) and `StockAlerter` (periodic alert checks). Serves both REST API (`/api/*`) and the built frontend static files from `backend/static/`.
- **`monitor.py`** — `StockMonitor` class. CRUD for tracked stocks, background auto-refresh loop (30s timer; skips US stocks during CN/HK market hours 09:30-16:00 Beijing time to respect Finnhub rate limits), per-stock refresh, and batch refresh with progress tracking via `task_id`.
- **`data_fetcher.py`** — `DataFetcher` class with static methods. Multi-market data pipeline:
  - US: Finnhub API (`/quote`, `/stock/metric`, `/stock/profile2`) — requires `FINNHUB_API_KEY`
  - CN: 东方财富 push2 API (real-time quote) + K-line API (52-week high/low from 300 weekly candles, `fltt=1` = price in 分/100)
  - HK: 东方财富 with `fltt=2` (price already correct scale), secid format `116.00xxx`
  - Falls back to built-in `DEMO_DATA` dict when API calls fail or no key is set
  - `detect_market()`: 6-digit numeric → CN, 1-5 digit numeric → HK, `.HK` suffix → HK, else US
- **`alerter.py`** — `StockAlerter` background thread (interval: `ALERT_CHECK_INTERVAL`, default 300s). Checks each stock's drawdown against its threshold; deduplicates per-ticker per-day via `alert_history` table; stores unread alerts in `alert_unread` table.
- **`briefing.py`** — 每日简报（Daily Briefing）。`BriefingGenerator`：采集当日股票快照（`stock_snapshots` 表）→ 组装上下文（含与上一份快照的"昨今对比"）→ 调用 LLM（OpenAI 兼容接口，`LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` 配置）生成 markdown 简报；无 Key 或调用失败时自动降级为确定性模板。`BriefingScheduler`：daemon 线程每 60s 检查，北京时间到点（`BRIEFING_TIME`，默认 08:30）且当日未生成则触发。简报存 `briefings` 表（每天一条，REPLACE）。API：`GET /api/briefings/`、`GET /api/briefings/latest`、`GET /api/briefings/{id}`、`POST /api/briefings/generate`。
- **`database.py`** — SQLite at `data/sentinel.db`. Creates `stocks`, `settings`, `alert_history`, `alert_unread`, `stock_snapshots`, `briefings` tables on init. Includes ad-hoc column migrations via `ALTER TABLE ADD COLUMN` with try/except.
- **`models.py`** — Pydantic v2 request/response models (`StockResponse`, `AddStockRequest`, `UpdateStockRequest`).

### Frontend (`frontend/`)

- React 19 + Vite + Tailwind CSS v4. Single page: `Dashboard.jsx` containing the full monitoring UI.
- Vite dev server proxies `/api` to `http://127.0.0.1:8000`.
- `vite build` outputs to `../backend/static/`, so the backend can serve the SPA directly.

### Data flow

1. User adds a stock via API → `StockMonitor.add_stock()` calls `DataFetcher.get_stock_info()` → writes to SQLite.
2. Auto-refresh polls data sources every 30s (US gated by market hours), updating DB rows.
3. `StockAlerter` checks all stocks every N seconds — if drawdown exceeds threshold and no alert today, stores an unread alert.
4. Frontend polls `/api/stocks/` and `/api/alerts/count` for live updates.

### Key design decisions

- **No ORM** — raw SQL via `sqlite3` with `row_factory = sqlite3.Row`.
- **Threading, not async** — background refresh and alert loops use `threading.Thread` / `threading.Timer`. The FastAPI app runs synchronously.
- **Demo data fallback** — all markets degrade gracefully to hardcoded data when APIs are unavailable or unconfigured.
- **52-week high/low** for A-shares and HK is computed client-side from up to 300 weekly K-line candles from EastMoney.

## Agent skills

### Issue tracker

Local markdown — issues live in `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` at repo root, `docs/adr/` for architectural decisions. See `docs/agents/domain.md`.
