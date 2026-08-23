# PRD: 同花顺金融数据 API 接入（fuyao.aicubes.cn）

Status: ready-for-agent（骨架已完成，待 API Key 验证后转 done）
Owner: agent
Version: 1.0
Date: 2026-08-20

## 概述

接入同花顺官方结构化金融数据 API（REST + MCP 双形态，`X-api-key` 鉴权，统一 `ApiResponse` 信封：
HTTP 恒 200，业务 code 表达）。数据质量高于爬虫级源，直接补齐当前因子管线的成长/质量缺口。

## 调研结论（已实测文档站）

| 接口 | 形态 | 用途 |
|---|---|---|
| `GET /api/a-share/valuations/snapshot` | 批量 ≤100 thscodes/次 | 全 A 股 PE-TTM/MRQ、PB、PS、PCF → 估值因子 |
| `GET /api/a-share/financials/indicators` | 单股 + 报告期 yyyy-1/2/3/4 | 成长/盈利/偿债/营运/现金流五类指标 → **ROE/ROA/毛利率/净利率/负债率/营收利润增速** |
| `GET /api/a-share/prices/snapshot` | 批量或全市场分页 | 行情快照（备用） |
| `GET /api/a-share/calendar`、`corporate-actions`、`special-data`、`a-share-index` | - | 日历/分红事件/异动原因/指数成分（后续） |

错误码：0 成功 / 1001 缺参 / 1002 report 非法 / 2001 无或无效 key / 2003 无权限 / 5002-5003 上游异常。

## 已完成（骨架，commit 待定）

- `quant_engine/data_source/ths_source.py`：
  - `THSApiClient`：X-api-key 会话、信封解析、错误码翻译
  - `valuations_snapshot(thscodes)`：自动 ≤100 分批
  - `financial_indicators_mapped(thscode, report)`：index_id → 因子列映射（`INDICATOR_MAP`）
  - `THSValuationFactorSource`：因子源（代码表复用本地 `ts_universe_cache`），
    已进 SOURCES 链（Tushare → **THS 估值** → 东财延时 → …），`required_env="THS_API_KEY"` 守卫
- `test_ths_source.py` 6/6：信封/分批/错误码/指标映射/因子源
- `.env.example` 增补 `THS_API_KEY`

## 待 Key 到达后

1. `THS_API_KEY` 写入 `backend/.env`（gitignored）— ✅ 用户已配置
2. 验证：`valuations_snapshot` 真实调用（确认免费额度/限流）— ✅ 实测 200，返回真实估值
3. `refresh_universe()` 真实刷新 → 确认因子数据 source=ths_valuations — ✅ 5549 只全量，16645 因子行
4. 财务指标 enrichment：个股级（监控列表/选股候选 Top N 逐股拉指标补 ROE/毛利率/增速），
   全市场逐股拉太重，先做按需 — ⏳ 下一步
5. 事件/日历/异动归因接入（后续迭代）

## 实测修正记录

- 估值响应字段为 `pb_mrq`（非 `pb`）→ 源内映射 pb_mrq → pb
- `latest_report` 按**披露日历**修正（1-4 月→上年年报、5-9 月→中报、10-12 月→三季报），
  并新增 `financial_indicators_latest` 自动回退上一期（当期未披露返回 5003 empty 时）
- THS 估值 df 补 `name` 字段
- 实测（2026-08-20）：茅台 PE-TTM 19.54/PB 6.33、平安 PE 5.09/PB 0.47，与东财延时源交叉一致；
  财务指标：茅台毛利率 89.76%/ROE 10.57、宁德 ROE 12.08/毛利率 23.93、平安负债率 90.98

## Todo

- [x] 客户端 + 估值因子源 + 单测（commit 92f78a8，7/7）
- [x] key 验证 + 全市场真实刷新（16645 因子行）
- [ ] 财务指标 enrichment（个股级按需）
- [ ] 事件/日历/异动归因接入

## 风险与待确认（需人）

- **免费额度/限流未知**：文档未公开定价，Key 签发页可见（用户确认中）
- 财务指标为单股接口，全市场刷新成本高（5552 次调用），设计为按需 enrichment
