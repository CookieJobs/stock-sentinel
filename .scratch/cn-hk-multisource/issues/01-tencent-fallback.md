# Issue 01: CN/HK 行情腾讯数据源 + 自动降级

Status: ready-for-agent

## What to build

`data_fetcher.py` 新增腾讯行情源，CN/HK 分支东财失败时自动降级到腾讯，都失败才回退 demo。
端到端打通：腾讯实时报价（GBK 解析）+ 腾讯周 K 计算 52 周高低点 → 返回与东财相同形状的 dict。

## Acceptance criteria

- [ ] `_tencent_secid`：CN `600519`→`sh600519`、`000001`→`sz000001`、`300750`→`sz300750`；HK `00700`→`hk00700`
- [ ] `_get_tencent_quote` 返回 `source=="tencent"`，含 current_price/change_pct/name/week52_high/week52_low/drawdown/pe_ratio 等完整字段
- [ ] CN/HK 东财失败时自动走腾讯（mock 东财返回 None 验证），都失败回退 demo
- [ ] `python3 backend/test_data_fetcher.py` 全部通过

## Blocked by

None - can start immediately
