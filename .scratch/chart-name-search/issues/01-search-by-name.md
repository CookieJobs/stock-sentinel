# Issue 01: /chart 股票名称搜索 + 名称/代码同显

Status: done

## What to build

1. 后端 `search_service.py`：东财 suggest API（免 key，沪深港美，代码/中文名/拼音）→ 市场规则过滤 → 本地
   降级（stocks / ts_universe_cache / daily_metrics 按名称 LIKE）→ (market, ticker) 去重。
2. 新路由 `GET /api/quant/search?q=&limit=&market=`（q 必填，limit 上限 20）。
3. 前端 `/chart`：搜索框联想下拉（防抖 300ms，每行 名称+代码+市场徽标，点击跳转）；
   纯代码回车保持原行为；页头「名称 + 代码」同显（深链反查，查不到退化仅代码）。

## Acceptance criteria

- [x] `GET /api/quant/search?q=茅台` 返回 贵州茅台(600519, CN)；`q=腾讯` 返回 腾讯控股(00700, HK)
- [x] `q=00700&market=HK` 只返回港股 00700（不混入 A 股 000700）
- [x] 东财不可达时降级本地库仍有结果（mock 验证）；两源合并按 (market, ticker) 去重
- [x] 前端输入「茅台」出现下拉（名称+代码+市场），点击后 URL 变 `?ticker=600519` 且页头显示「贵州茅台 600519」
- [x] 输入纯代码（600519 / AAPL / 00700）回车仍直接查询
- [x] 后端 `test_search.py` 全过；前端 lint + build 通过

## Blocked by

None - can start immediately

## Comments

- 2026-08-24：PRD 定稿。东财 suggest 实测：`茅台`→600519、`腾讯`→00700、`AAPL`→苹果；
  市场过滤规则按 MktNum/SecurityType/TypeUS 归纳（CN A/B 股 1-4、HK 正股 6/19+TypeUS3、US 普通股/ADR/ETF 1-5）。
- 2026-08-24：完成（commit ce4b022 后端 + f5ce5dc 前端）。踩坑记录：东财 suggest 用 `requests`（含
  `data_fetcher._em_get`）会被 CDN 按 TLS 指纹路由到 2023 年陈旧 JSONP 缓存（passport 残留），必须 urllib
  直连；本地降级源（自选表/ts_universe_cache/daily_metrics）实测能兜底 茅台/腾讯/AAPL。
  验证：test_search 25/25、全套 227 passed（5 个既有失败为沙箱写 ~/tk.csv 权限问题，与本次无关）、
  lint/build 通过、:8000 重启后实测 茅台→600519 / 00700+HK→腾讯控股 / AAPL→苹果。
