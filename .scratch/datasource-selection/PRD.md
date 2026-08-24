# PRD: 数据源选择 + 移除 Demo 假数据

Status: ready-for-agent
Owner: agent
Version: 1.0
Date: 2026-08-20

## 概述

两件事：
1. **数据源选择**：按数据域（实时行情 / 因子 / K线）可配置数据源，支持 `auto`（现状自动降级链）
   或手动钉住某个源（失败仍回退）。
2. **移除全部 demo 假数据**：`DEMO_DATA` / `MockFactorSource` / `_dynamic_demo_price` 全删，
   所有数据域失败时**诚实返回失败**（None / 空），不展示假数据。

## 数据域与可选源

| 域 | 配置键 | 可选值 | 说明 |
|---|---|---|---|
| 实时行情 realtime | `datasource.realtime` | auto / eastmoney / tencent | CN/HK；美股恒为 finnhub |
| 因子 factor | `datasource.factor` | auto / tushare / ths / eastmoney_delay / baostock / akshare | 移除 mock 后链末为 akshare |
| K线 kline | `datasource.kline` | auto / ths / akshare / baostock / eastmoney | CN；其他市场维持现链 |

## Implementation Decisions

- 新模块 `backend/datasource_config.py`（backend 根，供 data_fetcher 与 quant_engine 共用）：
  `get_config() / set_config(domain, source) / get_override(domain)`，存 `settings` 表
  （key=`datasource.<domain>`，value=`auto` 或源名）。
- 生效语义：**钉住的源排到链首优先尝试**，失败仍按原链降级（不锁死）。
  - 因子：`refresh_universe` / `get_factor_source` 按覆盖重排 SOURCES
  - K线：`data_source.get_kline` 按覆盖重排
  - 实时行情：`data_fetcher.get_stock_info` CN/HK 分支按覆盖调换 eastmoney/tencent 顺序
- API：`GET /api/quant/datasource/config`（含各域当前值 + 可选源列表）、
  `PUT /api/quant/datasource/config`（body `{realtime: "tencent", ...}`，非法值 400）。
- 前端：新增 `/settings` 页（三个下拉 + 保存），导航「⚙️ 数据源」。

## Demo 移除范围

- `data_fetcher.py`：删 `DEMO_DATA`、demo 回退分支、`_dynamic_demo_price`、`source="demo"`；
  全部失败返回 None（调用方如实报错）。✅
- `factor_source.py`：删 `MockFactorSource`；SOURCES 移除；`get_factor_source` 全失败返回 None。✅
- `api/factors.py`：行业列表改为查 daily_metrics 去重行业（不再用 Mock 静态表）。✅
- `monitor.py`：删 demo 守卫（死代码）；`_record_price_point` 简化。✅
- `paper_service.py`：demo 拒绝逻辑改为「无真实行情拒绝成交」。✅
- 测试同步：test_data_fetcher（demo 段改「全失败→None」）、test_paper_service、test_price_history。✅
- 文档：CLAUDE.md 删「Demo data fallback」决策项；PaperTrading 页文案。✅

## Todo

- [x] 数据源选择：backend 配置模块 + 三链接入 + API + /settings 页（commit 0769eb7）
- [x] Demo 移除（commit a830b2a）
- [x] 测试：test_datasource_config 3/3 + 全量回归 168 passed + lint/build

## Testing Decisions

- `test_datasource_config.py`：配置读写、非法值拒绝、三域重排逻辑（mock 源类）。
- 既有测试全量回归；前端 lint + build。
