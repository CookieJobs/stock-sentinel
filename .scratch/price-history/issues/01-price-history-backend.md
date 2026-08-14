# Issue 01: 后端价格历史落库（表 + 采样 + 时间桶 + 保留清理）

Status: done

## 描述

新增 `price_history` 表并在股票刷新拿到真实数据时落库，作为回撤趋势图的底层数据源：
1. `database.py` 追加 `price_history` 表（含 `(ticker, bucket)` 唯一约束与索引，见 PRD）
2. `monitor.py` 新增 `_record_price_point(data)`：真实数据（`source != 'demo'`）成功更新 `stocks` 后写入一行
3. 时间桶按北京时间对齐 15 分钟，同桶 `INSERT OR REPLACE` 幂等
4. 保留策略：写入时顺带清理超过 `PRICE_HISTORY_RETENTION_DAYS`（默认 90）天的旧行
5. demo 回退数据不落库

## 验收条件

- [ ] `python3 backend/test_price_history.py` 全部通过（含：落库字段齐全、同桶幂等、桶计算正确、demo 不落库）
- [ ] `_fetch_one_stock` 真实数据路径会写入 `price_history`，demo 路径不写
- [ ] 90 天前的旧行会被清理（写入时惰性触发）
- [ ] `python3 backend/test_data_fetcher.py` 仍全部通过（无回归）

## Blocked by

None - can start immediately

## Comments

- 2026-08-14：完成（commit 87536c2）。`database.py` 新增 `price_history` 表 + 索引；`monitor.py` 新增 `_price_bucket`/`_record_price_point`（15 分钟桶幂等、demo 不落库、写入时惰性清理 90 天前旧行）；`test_price_history.py` 6/6 通过。提交时用过滤 diff 只暂存本 issue 改动，未卷入工作区未提交的 demo 守卫改动。
