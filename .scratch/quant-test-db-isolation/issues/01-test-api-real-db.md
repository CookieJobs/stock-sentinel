# Issue 01: 量化测试套件污染真实 DB（test_api 用真实 sentinel.db 而非临时库）

Status: ready-for-agent

## 描述

`backend/tests/quant_engine/test_api.py` 的 fixture 直接 `from main import app` +
`init_quant_db()`，**跑测试会读写真实 `data/sentinel.db`**：

- `test_factors_refresh` 会真的跑一遍数据源链（BaoStock/AkShare/Mock），
  把 Mock 生成的因子数据（3853 只 × 6 因子）写进真实库；
- 每次全量跑 137 测试都会清掉当日 factor_values 再写入，污染/覆盖用户真实数据；
- 与本机其他测试（`test_briefing.py` / `test_price_history.py` 用临时 DB 隔离）风格不一致。

（2026-08-15 验证合并时实测：跑完 pytest 后真实库 `factor_values` 出现 23118 条
trade_date=当日 的 Mock 数据。）

## 建议方案

1. fixture 用临时 DB：monkeypatch `quant_engine.db` 的 DB 路径（或设置环境变量指向
   `tmp_path`），TestClient 用 `with TestClient(app)` 生命周期避免启动后台线程；
2. 或至少给 `test_factors_refresh` 打标记（如 `@pytest.mark.network` / 默认跳过），
   避免本地测试触发真实网络 + 写库；
3. 验收：`pytest backend/tests/ -q` 跑完后 `data/sentinel.db` 的
   `factor_values` / `daily_metrics` 行数不变。

## 验收条件

- [ ] 跑完 137 测试后真实库无新增/覆盖（对比跑前快照）
- [ ] `test_factors_refresh` 仍通过（用临时库或 mock 数据源）
- [ ] 不破坏其他 136 个测试
