# PRD: CN/HK 行情多数据源降级（EastMoney → 腾讯）

Status: ready-for-agent
Owner: agent
Version: 1.0
Date: 2026-08-19

## Problem Statement

A股/港股实时行情**只依赖**东财 `push2/push2his.eastmoney.com`。实测（2026-08-19）该接口在多种 Clash
配置下都被服务端秒断（`RemoteDisconnected`，http/https/http2/完整浏览器头均无效），导致 `data_fetcher`
静默回退 `DEMO_DATA` 假数据。用户希望行情获取**不依赖 Clash 配置**、不依赖单一域名。

## Solution

给 CN/HK 行情加**多数据源自动降级**：优先东财，失败自动切腾讯行情（`qt.gtimg.cn` 实时 + `web.ifzq.gtimg.cn`
周 K 计算 52 周高低点），腾讯也失败才回退 demo。腾讯/新浪是普通国内 CDN，实测在用户各种 Clash 配置下均
200 通，且与东财无耦合——任一源被风控/代理搞挂，另一个顶上，达到「基本免疫 Clash 配置」的效果。

## User Stories

1. 作为用户，我希望 A股/港股行情在单个数据源不可用时自动换源，而不是显示 demo 假数据。
2. 作为用户，我希望行情获取不因 Clash 代理配置而失效。
3. 作为用户，我希望每个来源都带 `source` 标记（eastmoney/tencent/demo），以便信任数据。

## Implementation Decisions

- **数据源**：
  - 腾讯实时：`https://qt.gtimg.cn/q=<code>`（GBK 编码，`~` 分隔；CN 用 `sh/sz` 前缀，HK 用 `hk` 前缀）
    - 字段：1=名称、3=现价、32=涨跌幅%、39=PE(TTM)（CN）/ 不同位置（HK）
  - 腾讯周 K（52 周高低点）：`https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=<code>,week,,,320,qfq`
    - 每根 bar：`[date, open, close, high, low, volume, ...]`；取 320 根内的 max(high)/min(low) 及对应日期
- **代码结构**（`backend/data_fetcher.py`）：
  - 新增 `DataFetcher._tencent_secid(ticker, market)`：CN → `sh`/`sz` + 6 位；HK → `hk` + 5 位。
  - 新增 `DataFetcher._get_tencent_quote(ticker, market)`：一次拉实时 + 周 K，返回与东财相同形状的 dict，
    `source="tencent"`。
  - `get_stock_info` 的 CN/HK 分支：先 `_get_eastmoney_*`，失败（返回 None）再 `_get_tencent_quote`，
    都失败才回退 demo。
- **不删东财**：保留为第一优先级（数据更权威），腾讯做降级；`source` 字段已区分，前端无需改。

## Testing Decisions

- 只测外部行为：腾讯 source 返回结构完整、52 周高低点计算正确、CN/HK 前缀映射正确、东财失败时自动降级。
- 新增用例并入 `backend/test_data_fetcher.py`（沿用确定性 mock 风格：mock 东财返回 None → 断言走腾讯；
  腾讯解析用真实返回片段或最小 mock）。
- 前端无改动，无需 build；但需 `test_data_fetcher.py` 全过。

## Out of Scope

- 新浪源、美股 Finnhub 多源（本次只做 CN/HK 的东财→腾讯）。
- 东财 push2 风控逆向（另见 `.scratch/eastmoney-proxy/PRD.md`）。
- K 线/因子数据源（`quant_engine` 已有 AkShare/BaoStock 多源链，不在本次范围）。

## Further Notes

- 腾讯报价 GBK 编码，需 `resp.content.decode('gbk', errors='ignore')`。
- HK 腾讯周 K 的 bar 可能带分红除权信息（第 7 元素为 dict），解析时只取前 6 个标量。
- 该改动让 v0.2.0 行情脱离对 push2 的单一依赖，与 `_NAME_MAP`/`_SECTOR_MAP` 兜底思路一致。

## Todo

- [x] `01-tencent-fallback.md` — 腾讯数据源 + 东财→腾讯自动降级
