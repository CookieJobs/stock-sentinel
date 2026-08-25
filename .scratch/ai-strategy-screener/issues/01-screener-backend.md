# Issue 01: AI 策略选股 — 后端（策略库 + API + 因子白话）

Status: done

## What to build

新手友好的选股策略后端：
1. `quant_engine/screener_strategies.py`：6 个内置策略（名字/tagline/适用人群/风险标签/
   filters/rank_by/top_n/条件白话解释）+ `get_strategies()` + `validate_strategy()` +
   `generate_strategy(prompt)`（LLM，复用 briefing 的 `LLM_API_KEY` 配置，失败抛业务错误）
   + `apply_strategy()`（整列为空的筛选因子自动跳过 → 调 `factor_service.screen`）。
2. `quant_engine/api/screener.py`：`GET /strategies`、`POST /strategies/generate`
   （`{prompt}`，校验失败/LLM 不可用 → 400 + 友好中文消息）、`POST /screen`
   （`{strategy_id}` 或 `{strategy}`，响应附加 `skipped_factors`）；注册进
   `quant_engine/api/__init__.py`。
3. `quant_engine/factors.py`：`FACTOR_EXPLAINERS`（15 因子大白话 + unit），
   `list_factors()` 输出追加 `description_zh` / `unit`（additive）。
4. 测试 `tests/quant_engine/test_screener_strategies.py`：策略结构校验、副本隔离、
   apply_strategy 空列跳过、LLM 生成校验（monkeypatch）、3 端点集成冒烟。

## Acceptance criteria

- [ ] `GET /api/quant/screener/strategies` 返回 ≥6 个策略，每个含 name/tagline/filters/rank_by/top_n/explains，附 `llm_configured`
- [ ] `POST /api/quant/screener/strategies/generate`：LLM 返回合法 JSON → 返回策略；坏 JSON/未知因子/超范围 → 400；无 Key → 400 中文提示
- [ ] `POST /api/quant/screener/screen`：按 strategy_id 执行选股；整列为空的因子跳过并出现在 `skipped_factors`
- [ ] `/api/quant/factors/list` 每项含 `description_zh` + `unit`，15 个因子全覆盖
- [ ] `pytest backend/tests/quant_engine/test_screener_strategies.py -q` 全过；全量 pytest 不破坏现有 172 个测试

## Blocked by

None - can start immediately

## Comments

- 2026-08-26：PRD `.scratch/ai-strategy-screener/PRD.md` 已就绪。
- 2026-08-26：完成（commit 7e1f133）。6 内置策略 + 校验 + LLM 生成（复用 briefing
  配置，无 Key 友好 400）+ apply_strategy（空列跳过 / desc 因子默认 min=0 排负值 /
  applied_filters 透明返回）。test_screener_strategies.py 32/32 通过；全量
  quant_engine 229 passed（3 个既有 ~/tk.csv 沙箱失败除外）。
