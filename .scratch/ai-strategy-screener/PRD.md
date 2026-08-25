# PRD: AI 策略选股（新手友好的选股器）

Status: ready-for-agent
Owner: agent
Version: 1.0
Date: 2026-08-26

## Problem Statement

`/screener`（M3 多因子选股）是纯指标驱动：用户要自己理解 PE/PB/ROE/毛利率等指标、
自己组合条件、自己选排名方式。对投资小白，这些指标是黑话——「PE 是什么？怎么算便宜？
该筛多少？」。结果是**新手根本用不起来选股器**。

用户明确诉求：**AI 给出几种选股策略 → 用户选一个策略 → 按策略自动选股**。
原则：让小白用户也能用明白这个平台。

## Solution

在 Screener 页引入「✨ AI 策略选股」作为默认（新手）入口：

1. **内置策略卡**（专家预写，确定性、无 Key 也可用）：
   每个策略 = 名字 + 一句话白话 tagline + 适用人群 + 风险标签 + 过滤条件组
   （filters + rank_by + top_n）。点「用这个策略选股」一键执行。
   每张卡可展开：**每个条件都用大白话解释**（如「PE ≤ 25：市盈率 = 股价 ÷ 每股赚的钱，
   越小代表回本越快、越便宜」）。
2. **AI 自然语言生成策略**（复用 briefing 的 LLM 配置，`LLM_API_KEY` 缺失时优雅降级）：
   用户输入「我想找稳定赚钱、估值不贵的大公司」→ LLM 返回结构化策略 JSON →
   后端严格校验（因子必须存在于 FACTOR_REGISTRY、数值范围合法）→ 生成一张新策略卡。
3. **手动高级模式**（保留现有功能，折叠到「高级」标签下）：老用户/进阶用户仍可
   手调条件。
4. **因子说明白化**：`/factors/list` 增加每个因子的 `description_zh`（大白话）
   与 `unit`（单位），前端因子说明区直接展示。

### 数据单位问题（本 PRD 顺带处理）

实测当前库：ROE/毛利率以**百分比**存储（美的 5.56 = 5.56%），而现有前端按小数 ×100
显示（会显示 556%）——新手看到的第一印象就错了。且 roe/gross_margin 目前只有约 20 只
有值（THS 只 enrich 自选股），revenue_yoy/profit_yoy/turnover_rate/market_cap 为空。

处理：
- 策略执行时对**整列为空**的筛选因子自动跳过（响应里返回 `skipped_factors` 说明），
  不因数据缺失静默返回 0 只。
- 结果表显示归一化：`value > 1` 视为百分比原值直接显示，否则 ×100（兼容两种存储单位）。
- 单位不归一化的根治（数据源层统一转小数）记为一个独立 follow-up issue，不在本 PRD
  范围内动数据源。

## User Stories

1. 作为小白用户，我想看到几张「人话」策略卡（如「便宜又赚钱的好公司」），点一下就能
   选出股票，以便不学指标也能用选股器。
2. 作为小白用户，我想看每个条件的白话解释，以便知道策略在筛什么。
3. 作为有想法但不懂指标的用户，我想用一句话描述我要的股票（如「低估值的高分红股」），
   AI 帮我翻译成选股条件，以便把想法变成可执行的策略。
4. 作为进阶用户，我仍想手动调条件，以便保留原有能力。
5. 作为没有 LLM Key 的用户，内置策略 + 白话解释全部可用，以便功能不依赖外部服务。
6. 作为用户，我不想因为某个因子没数据（如换手率为空）就得到 0 只结果，以便策略
   在数据不全时仍然诚实可用。

## 内置策略（初版 6 个）

| id | 名字 | 核心条件（单位按当前库：%为百分比，其余为倍） | 排名 | 风格 |
|---|---|---|---|---|
| `value_quality` | 🛒 便宜又赚钱的好公司 | PE 0~25, PB 0~4, ROE ≥ 12 | roe | 价值质量 |
| `steady_growth` | 🌱 稳健成长股 | PE 0~40, ROE ≥ 15, 毛利率 ≥ 30 | roe | 成长质量 |
| `deep_value` | 🏦 深度低估 | PE 0~15, PB 0~2 | pe_ttm | 深度价值 |
| `big_stable` | 🏔 大盘稳健蓝筹 | PE 0~30, PB 0~5, ROE ≥ 10 | market_cap | 大盘价值 |
| `quality_moat` | 🏰 高毛利护城河 | 毛利率 ≥ 40, ROE ≥ 12, PE 0~50 | gross_margin | 质量 |
| `low_debt_safe` | 🛡 低负债稳如泰山 | 负债率 0~40, PE 0~30, ROE ≥ 8 | debt_ratio | 防御 |

> 条件用"或松"策略：整列为空的因子自动跳过（见数据单位问题一节），
> 保证当前数据下多数策略有结果。`big_stable` 在 market_cap 为空时退化为纯 ROE/PE 筛选。

## API 设计

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/quant/screener/strategies` | GET | 内置策略列表 + `llm_configured` |
| `/api/quant/screener/strategies/generate` | POST | `{prompt}` → LLM 生成策略（校验后返回） |
| `/api/quant/screener/screen` | POST | `{strategy_id}` 或 `{strategy}` → 执行选股（复用 factor_service.screen，附加 skipped_factors） |

`GET /api/quant/factors/list` 增加 `description_zh` + `unit` 字段（additive，不破坏现有消费方）。

## 实现

- `quant_engine/screener_strategies.py`：SCREENER_STRATEGIES 静态数据 + get_strategies()
  + validate_strategy() + generate_strategy(prompt)（LLM，无 Key/失败抛业务错误）
  + apply_strategy()（过滤空列因子 → 调 factor_service.screen）。
- `quant_engine/api/screener.py`：3 个端点；`api/__init__.py` 注册。
- `quant_engine/factors.py`：FACTOR_EXPLAINERS（15 因子白话 + 单位）并入 list_factors()。
- 前端 `Screener.jsx` 重构：模式切换（AI 策略 / 手动高级）；策略卡网格 + 展开解释；
  自然语言输入 + AI 生成；结果表（含 skipped_factors 提示）；因子说明区显示白话。
- `lib/api.js`：screener 三个端点封装。

## 测试

- `test_screener_strategies.py`：
  - 策略结构校验（id 唯一、因子均在 FACTOR_REGISTRY、min≤max、top_n 范围）10+ 条
  - get_strategies 返回副本
  - apply_strategy：空列因子跳过 + skipped_factors 返回 + 正常过滤（临时库造数）
  - generate_strategy：monkeypatch LLM 成功/坏 JSON/未知因子 → 校验拦截
  - API 集成：3 端点冒烟（GET strategies、POST screen by id、generate 无 Key 时 400）
- 全量 pytest + 前端 lint/build。

## 非目标（明确不做）

- 不改数据源层单位（follow-up issue）
- 不做策略持久化/用户自定义保存（v2）
- 不做策略回测联动（点策略卡直接可选「回测此策略」留给 v2）
- 不引入新依赖 / 新外部服务（LLM 复用 briefing 配置）

## Todo

- [x] PRD
- [x] issues 拆分
- [x] 后端 screener_strategies.py + API + 测试
- [x] 前端 Screener 重构 + api.js
- [x] 全量验证（pytest / lint / build）
- [x] CHANGELOG + 收工汇报

## Comments

- 2026-08-26：完成（commit 7e1f133 后端 + c890b83 前端）。
  实现要点：desc 因子（PE/PB/负债率）未给 min 时默认 min=0 排除负值（否则
  「深度低估」把负 PE 亏损股排最前）；整列为空因子自动跳过 + skipped_factors
  如实返回；ROE/毛利率显示归一化（兼容 % 与小数两种存储）。真实库冒烟：
  deep_value 返回动力新科/贵阳银行等正 PE 低估股；generate 无 Key 返回友好 400。
