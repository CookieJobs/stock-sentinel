# PRD: /chart 股票名称搜索 + 名称/代码同显

Status: done
Owner: agent
Version: 1.0
Date: 2026-08-24

## Problem Statement

`/chart` 页目前只能按**股票代码**搜索（`600519` / `AAPL` / `00700`），页面也只展示代码本身。
用户对不熟悉的代码无法用**股票名称**（中文名 / 拼音）找到目标，选中后也看不出这只股票叫什么。

## Solution

1. **后端新增股票搜索 API** `GET /api/quant/search?q=<关键词>&limit=10&market=CN|HK|US`：
   - 主源：东方财富 suggest API（`searchapi.eastmoney.com/api/suggest/get`，免 key，
     支持 沪深港美 的代码 / 中文名 / 拼音检索），按市场规则过滤（排除指数/债券/权证等）。
   - 降级源：本地 `stocks` 自选表 + `ts_universe_cache` + `daily_metrics`（按名称 LIKE）。
   - 返回 `{query, results: [{ticker, name, market, source}]}`，跨源按 (market, ticker) 去重。
2. **前端 `/chart` 搜索框升级为联想下拉**：
   - 输入即搜（300ms 防抖），下拉每行显示「名称 + 代码 + 市场徽标」，点击即跳转。
   - 输入纯代码回车保持原行为（直接查询）；输入名称回车选中第一条结果。
3. **页头展示「名称 + 代码」**：选中后显示如「贵州茅台 600519 · 🇨🇳 A股」；
   深链/刷新时用搜索接口按 (ticker, market) 反查名称，查不到则退化为仅代码。

## User Stories

1. 作为用户，我可以输入「茅台」/「MAOTAI」/「腾讯」找到并打开对应股票的 K 线图。
2. 作为用户，我在图表页能一眼看到当前股票的中文名称和代码，而不只是代码。
3. 作为用户，我仍然可以像以前一样直接输入代码回车查询。

## Implementation Decisions

- **东财 suggest 过滤规则**（实测 2026-08-24 归纳）：
  - CN：`MktNum` ∈ {0,1} 且 `SecurityType` ∈ {1,2,3,4}（沪深 A/B 股，排除指数 5 / 债券 16）
  - HK：`MktNum` = 116 且 `SecurityType` ∈ {6,19} 且 `TypeUS` = 3（正股；6+TypeUS2 是债券）
  - US：`MktNum` ∈ {105,106,107} 且 `TypeUS` ∈ {1,2,3,4,5}（含普通股/ADR/ETF，排除 Notes 6）
- **token 参数**：`D43BF722C8E33BDC906FB84D85E326E8` 是东财前端公开常量，非密钥。
- **HTTP 复用** `data_fetcher._em_get`（https 优先自动降级 http），超时 6s，失败静默降级本地。
- 名称反查与搜索共用同一接口：`q=<ticker>&market=<m>` 精确匹配。

## Out of Scope

- 其他页面（Dashboard/Screener/Portfolio）的搜索改造。
- 拼音首字母高亮、模糊打分排序等增强（东财 suggest 已按相关性排序）。

## Todo

- [x] 后端 search_service + `/api/quant/search` 路由（含 422 校验）
- [x] 后端单测（分类规则 / 多源合并去重 / 降级 / API 集成）
- [x] 前端 api.js `search` 封装
- [x] 前端 Chart.jsx：联想下拉 + 页头名称/代码同显
- [x] 验证（pytest / lint / build）+ 提交 + 更新 CHANGELOG
