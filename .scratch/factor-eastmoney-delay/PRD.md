# PRD: 东财延时行情因子源（Factor Source: EastMoney Delay）

Status: done
Owner: agent
Version: 1.0
Date: 2026-08-20

## Problem Statement

因子数据唯一可靠来源是 Tushare `daily_basic`，但当前 token 档位限制 **1次/分钟 + 1次/小时 + 5次/天**
（失败调用也计入），刷新频繁撞限流跌进 Mock 假数据；且 `fina_indicator`/`income` 无权限。

## Solution

调研发现 `push2delay.eastmoney.com`（东财**延时 15 分钟**行情）与 push2 同一套 API 形状但**不触发
push2 的服务端风控**（本机实测稳定 200，total=5552）。其 clist 接口可提供全 A 股：
价格/涨跌幅/换手率/**PE(动)/PE-TTM/市净率/总市值/流通市值/ROE/行业**。

新增 `EastMoneyDelayFactorSource` 接入因子降级链：

```
Tushare（有配额时优先）→ 东财延时（无 key 无配额）→ BaoStock → AkShare → Mock
```

## Implementation Decisions

- 新文件 `quant_engine/data_source/eastmoney_delay_source.py`：
  - clist 分页抓取（实测单页上限 100，共 ~56 页；**后段页偶发超时 → 每页重试 3 次 + 1s 退避**）
  - 字段映射：f12→ticker、f14→name、f100→industry、f115→pe_ttm（f9 动态 PE 兜底）、
    f23→pb、f116→ps_ttm（如返回）、f8→turnover_rate、f3→change_pct、
    f20/f21→market_cap/float_cap（元 → 万元，对齐 Tushare）、f37→roe
  - 缺失/`-` 值 → NaN（不参与截面排名）
- `factor_service.refresh_universe`：**只有含因子列的 df 才算该源成功**——
  修复 Tushare 限流回退缓存返回"空壳 universe"时阻断降级链的问题。
- `factor_source.SOURCES`：`[Tushare, EastMoneyDelay, BaoStock, AkShare, Mock]`。

## Testing Decisions

- `test_eastmoney_delay_source.py`：mock clist 响应验证分页（100 行/页 × 2 页）、
  字段映射、ticker 补零、market 标记、市值单位换算、`-`→NaN、空响应。
- 真实验证：`refresh_universe()` → 21205 因子行；turnover_rate 5552 只完整，
  pe_ttm/pb/roe 5215+ 只；抽查茅台 PE 19.54/PB 6.33/ROE 16.75 为真实值。

## Out of Scope

- 财务深数据（gross_margin/revenue_yoy 等）仍缺：需 Tushare 升级或 BaoStock 网络恢复。
- K 线图表源加固（push2delay 的 kline/get 同样可用，另立 issue）。

## Further Notes

- 15 分钟延时对日频因子无影响。
- 免费档每天刷新一次即可（无配额概念），刷新前无需等待。
