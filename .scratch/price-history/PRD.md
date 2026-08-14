# PRD: 历史行情落库与回撤趋势（Price History & Drawdown Trend）

Status: ready-for-agent
Owner: agent
Version: 1.0
Date: 2026-08-14

## Problem Statement

StockSentinel 目前只保存股票的**当前快照**，没有任何历史价格轨迹。用户无法回答"回撤是怎么演变过来的"：
今天的 -25% 是一周内从 -10% 快速扩大，还是一直在 -25% 附近震荡？每日简报的「昨今对比」只有两天，
且依赖每天生成简报时才拍快照（`stock_snapshots` 每天每只仅一行），不足以支撑趋势分析。
SPEC（`.scratch/daily-briefing/SPEC.md` §10）已把「简报内嵌图表（回撤趋势线）」列为后续迭代，
其前置依赖就是**历史行情落库**。

## Solution

每次刷新拿到**真实数据**时，把价格/回撤写入新的 `price_history` 表（按 15 分钟时间桶去重，防止 30s 刷新周期产生冗余行）；
提供 `GET /api/history/{ticker}` 查询最近 N 天的回撤/价格序列；前端以纯 SVG sparkline 展示个股回撤趋势。
demo 回退数据**不落库**（与 `monitor.py` 已有"demo 不覆盖真实数据"的守卫语义一致）。

## User Stories

1. 作为用户，我想查看单只股票最近 30 天的回撤走势，以便判断回撤是突然扩大还是长期积累。
2. 作为用户，我想在 Dashboard 的股票列表里直接看到回撤趋势的小图，以便快速扫描组合里哪只票在持续恶化。
3. 作为用户，我想知道趋势数据来自真实行情而非 demo 假数据，以便信任图表。
4. 作为用户，我希望趋势数据保留一段时间（默认 90 天）且不无限膨胀数据库，以便系统长期运行不卡。
5. 作为用户，我希望历史行情成为简报内嵌趋势图（后续迭代）的底层数据源，以便每天简报直接附图。

## Implementation Decisions

- **新表 `price_history`**（`database.py` `init_db` 内追加，`CREATE TABLE IF NOT EXISTS`，符合无迁移工具风格）：

  ```sql
  CREATE TABLE IF NOT EXISTS price_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker TEXT NOT NULL,
      market TEXT,
      name TEXT,
      bucket TEXT NOT NULL,          -- 北京时间 YYYY-MM-DD HH:MM，对齐到 15 分钟
      current_price REAL,
      change_pct REAL,
      drawdown REAL,
      week52_high REAL,
      captured_at TEXT NOT NULL,     -- ISO 时间戳（北京时间）
      UNIQUE(ticker, bucket)
  );
  CREATE INDEX IF NOT EXISTS idx_price_history_ticker ON price_history(ticker, bucket);
  ```

- **采样时机**：`StockMonitor._fetch_one_stock` 中，真实数据（`source != 'demo'`）成功更新 `stocks` 后调用
  `_record_price_point(data)` 落一行；demo 数据直接跳过。手动刷新与自动刷新共用同一入口，天然都覆盖。
- **时间桶**：北京时间，分钟对齐 15：`bucket = f"{y:04d}-{m:02d}-{d:02d} {h:02d}:{(min//15)*15:02d}"`。
  同桶重复写入用 `INSERT OR REPLACE` 幂等覆盖（对齐 `stock_snapshots` 的既有风格）。
- **保留策略**：默认保留 90 天（env `PRICE_HISTORY_RETENTION_DAYS`，默认 90）。每次写入时顺带执行一次轻量
  `DELETE FROM price_history WHERE captured_at < 截止时间`（有索引，量小），无需额外后台任务。
- **新模块归属**：逻辑放 `monitor.py`（`StockMonitor._record_price_point` + 桶计算函数），
  不新建文件——与刷新流程内聚，且对齐"无 ORM、raw sqlite3 + threading"的既有模式。
- **API**（`main.py`）：
  - `GET /api/history/{ticker}?days=30` → `{"ticker", "market", "days", "points": [{"captured_at", "current_price", "change_pct", "drawdown", "week52_high"}, ...]}`，按时间升序；无数据返回空 `points`（200），不 404。
  - 路由注册在静态托管 catch-all 之前（同 briefing/alerts 的既有顺序约束）。
- **前端**（后续 issue）：Dashboard 个股行渲染纯 SVG sparkline（`<polyline>`，无新依赖），
  数据取 `drawdown` 序列；悬浮显示首末值。不引入图表库。

## Testing Decisions

- 只测外部行为：落库内容与幂等、桶计算、demo 跳过、API 返回结构——不测实现细节。
- 新文件 `backend/test_price_history.py`，沿用 `test_briefing.py` 先例：
  临时 DB（monkeypatch `database.DB_PATH`）+ `if __name__ == "__main__"` 轻量运行器 + FastAPI TestClient。
- 测试点：
  1. `_record_price_point` 写入一行，字段齐全（ticker/bucket/price/drawdown）；
  2. 同 ticker 同桶二次写入不新增行（幂等）；
  3. 桶计算：`2026-01-01 10:42`（北京时间）→ `2026-01-01 10:30`，`10:07` → `10:00`；
  4. `source == 'demo'` 的数据不落库；
  5. API 冒烟：先落一行 → `GET /api/history/{ticker}` 返回该点；无数据 ticker 返回空数组。

## Out of Scope

- 简报内嵌趋势图（下一迭代，依赖本功能的数据源）。
- 推送渠道、新闻归因（已有 `ready-for-human` issues，涉及外部服务）。
- 历史数据删除/管理 UI（保留策略自动清理即可）。
- 分钟级实时图表、多指标（成交量等）历史。

## Further Notes

- 落库只发生在 `_fetch_one_stock` 真实数据分支；当前工作区 `backend/data_fetcher.py`、`backend/monitor.py`
  有未提交改动（属人工排查实验），本功能不依赖、不修改、不提交它们。
- 与 `stock_snapshots` 的关系：快照是"每天一次"的简报输入（保留语义不同）；`price_history` 是"高频连续"
  的趋势数据源，两者并存、各司其职。
