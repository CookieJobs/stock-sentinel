## 2026-08-27 — 标签页名称更新为「股感」

- 页面标题从 `StockSentinel - 回撤监控` 更新为 `stock sentinel - 股感`，构建产物已同步到 `backend/static/`。
- 验证：`python backend/test_data_fetcher.py`、`python -m pytest backend/tests/ -q`（232 passed）、前端 lint + build 通过。

## 2026-08-27 — 浏览器标签图标改为 📈

- 将 SVG favicon 简化为原生 📈 emoji，替换此前的自绘折线图标；Vite 构建产物已同步到 `backend/static/`。
- 验证：`python backend/test_data_fetcher.py`、`python -m pytest backend/tests/ -q`（232 passed）、前端 lint + build 通过。

## 2026-08-26 — 风险关注提醒：一次越线、恢复后重置

- **语义统一**：回撤提醒改为显式开关 + 正数「关注线」，新增股票默认关闭；旧库的负数阈值平滑迁移为开启并取绝对值，零阈值仍关闭，历史记录不删除。
- **低噪音状态机**：首次从 52 周高点回撤越线才提醒；持续超限不再每日重复，回撤收窄至少 2pp 后才重新布防。提醒明确为关注信号，不构成买卖建议。
- **数据防线**：超过 120 分钟的行情（`ALERT_MAX_QUOTE_AGE_MINUTES` 可配）和 `≤ -95%` 的异常回撤不触发；`alert_history` 保存触发时的回撤、关注线和事件类型。
- **Dashboard**：添加/编辑页有独立开关，未启用项明确显示；提醒和历史面板显示首次越线与触发快照；修正最深回撤的排序和风险颜色。
- **验证**：`test_alerter.py` 7/7、`test_briefing.py` 6/6、`test_data_fetcher.py` 全过；量化套件中排除 Tushare 写 `/Users/liujin/tk.csv` 的既有沙箱限制后 **229 passed**；前端 lint + build 通过。

## 2026-08-26 — AI 策略选股：新手也能一键选股

- **新功能**（commit 7e1f133 后端 + c890b83 前端，`.scratch/ai-strategy-screener/`）：
  /screener 重构为双模式，默认「✨ AI 策略选股（推荐新手）」：
  - 6 个内置策略卡（人话名字 + tagline + 适用人群 + 风险标签 + 条件 chips），
    点「用这个策略选股」一键出结果，卡片可展开看每个条件的大白话解释。
  - 自然语言 AI 生成策略：一句话描述想要的股票（如「低估值的高分红股」）→
    LLM 转结构化策略 JSON 并严格校验（复用 briefing 的 OpenAI 兼容配置，
    无 Key 时友好提示，不依赖外部新服务）。
  - 手动高级模式保留 M3 全部原始功能；指标小词典改为大白话 + 单位。
  - 数据防御：整列为空的因子自动跳过并如实返回 `skipped_factors`；desc 因子
    （PE/PB/负债率）未给 min 时默认 min=0，排除负 PE 亏损股（否则「深度低估」
    把亏损股排最前）；ROE/毛利率显示归一化（兼容百分比/小数两种存储，修掉
    原 ×100 显示 556% 的问题）。
  - 测试：`test_screener_strategies.py` 32/32（结构校验 / LLM 生成 monkeypatch /
    空列跳过 / API 集成）；全量 quant_engine 229 passed（3 个既有 ~/tk.csv
    沙箱写拒绝失败除外）；lint + build 通过。
- **顺手修复**（commit 5095a5d，`.scratch/quant-test-db-isolation/`）：量化测试套件
  DB 隔离 — conftest 重定向临时库 + test_db_isolation 回归保护，跑 pytest 不再
  读写真实 `data/sentinel.db`。
- 注意：后端已重启生效；因子数据目前 roe/毛利率只有约 20 只有值（THS 只 enrich
  自选股），多数策略会显示「条件已跳过」提示，待因子源充实后自动生效。

## 2026-08-25 — /chart 股票名称搜索 + 名称/代码同显

- **新功能**（commit ce4b022 后端 + f5ce5dc 前端，`.scratch/chart-name-search/`）：
  /chart 页原来只能按代码搜索、只显示代码。现在：
  - 后端 `GET /api/quant/search?q=&limit=&market=`：东财 suggest API（免 key，支持
    代码/中文名/拼音缩写，覆盖沪深港美）主源 + 本地降级（stocks 自选表 /
    ts_universe_cache / daily_metrics），按 (market, ticker) 去重，按
    MktNum/SecurityType/TypeUS 过滤市场（排除指数/债券/Notes/权证）。
  - 前端搜索框联想下拉（300ms 防抖）：每行「名称 + 代码 + 市场」，点击即跳转；
    回车有候选时精确代码优先（00700→港股腾讯），无候选保持原直接查询行为。
  - 页头显示「名称 + 代码 + 市场」；深链/刷新按 (ticker, market) 反查名称。
- **踩坑**：东财 suggest 用 `requests` 会被 CDN 按 TLS 指纹路由到 2023 陈旧 JSONP 缓存
  （passport 残留），必须 urllib 直连（https→http 自动降级）。
- 测试：新增 `test_search.py` 25 个全过；全套 227 passed（5 个既有失败
  `test_factor_source`/`test_screener_strategies` 为沙箱写 `~/tk.csv` 权限问题，与本次无关）；
  前端 lint + build 通过；:8000 实测 茅台→600519、00700+market=HK→腾讯控股、AAPL→苹果。
- 未决：工作区另有他人未提交的 ai-strategy-screener 改动（screener.py 等），未纳入本次提交。

## 2026-08-25 — 站点图标改为上涨趋势 📈

- **图标换新**（commit aa893a6）：favicon.svg 折线方向反转（下降 → 上涨），端点圆点由
  红色警示改为绿色；App.jsx 侧边栏 logo emoji 📉 → 📈；构建产物同步。
- 验证：npm run lint + npm run build 通过。

## 2026-08-25 — 空数据周期清理旧 K 线 series（防旧图残留）

- **空数据周期清理**（commit a521812）：`StockChart.jsx` kline effect 在空数组时先
  removeSeries 旧 candle/volume 再返回，修复切到空数据周期（如 60m 源不可用）时
  「暂无数据」提示下残留上一周期旧图的问题（M2 起的老行为）。
- 验证：Playwright 截图像素对比 — 直开 60m 与从日 K 切换后 60m 的图表区均无 K 线色像素；
  lint + build 通过（产物同步）。

## 2026-08-25 — 后端 K 线序列化硬化（NaN/inf 清洗，防图表崩溃第二雷管）

- **K 线序列化硬化**（commit 8772d63）：`kline_service._to_float` 对 None/NaN/±inf 一律返回
  None（原实现 inf 穿透，JSON allow_nan=False 直接 500）；新增 `_is_finite` 过滤指标值
  （inf 会穿过 pd.notna）；`get_kline_with_indicators` 序列化前 replace(inf→nan) +
  dropna(OHLC 四列)；`ths_source._resample_kline` dropna 扩到四列（原只 close，THS
  to_numeric(errors='coerce') 产 NaN 时 open/high/low 的 NaN 组会存活 → JSON null →
  前端 lightweight-charts 断言 got=object 崩 K 线主图）。
- 测试：新增 test_kline_service_sanitize.py 7 个单测（_to_float/_is_finite/OHLC 行丢弃/
  inf 指标值过滤/重采样四列 dropna），7/7 通过；全量 172 passed（3 个 test_factor_source
  失败为沙箱写 ~/tk.csv 被拒，与本次无关）；test_data_fetcher.py ALL TESTS PASSED。
- 注意：后端需重启生效。

## 2026-08-25 — 图表防御加固（数据清洗 + 空数据提示）

- **图表防御加固**（commit bb5a54c）：`StockChart.jsx` K 线/成交量/指标 setData 前用
  `isFiniteBar`/`isFinitePoint` 过滤 NaN/undefined 值，防止脏数据直接进入 lightweight-charts
  触发断言崩溃（白屏根因的同族风险）；`Chart.jsx` 后端返回空 kline（如分钟周期数据源不可用）
  时显示「暂无数据」提示，不再静默空图。
- 验证：Playwright 实测 /chart 默认渲染 11 canvas 零错误；切 60m 显示暂无数据提示不崩；
  切回日 K 恢复；lint + build 通过（产物同步）。

## 2026-08-25 — 修复 /chart 页面白屏（MACD 振荡器崩溃 + 错误边界）

- **修复 /chart 白屏**（commit d5aab8f）：`StockChart.jsx` MACD.bar 振荡器原用 BarSeries 渲染但
  setData 缺 high/low，lightweight-charts v5 dev 构建断言 `Bar series item data value of high must
  be a number` 在 useEffect 内抛未捕获异常 → App 无错误边界 → React 卸载整棵组件树 → /chart 白屏
  （dev :5173）。缺陷自 M2 即存在，此前东财 K 线被风控返回空 → StockChart 早退不触发；8/23 接入
  同花顺 THS 源恢复 K 线后崩溃路径激活（回归）。修复：MACD 柱改用 HistogramSeries（数据只需
  {time,value}，删 BarSeries import）；根组件 Routes 外包 ErrorBoundary，页面异常显示错误卡片
  不再整页白屏。
- 验证：Playwright 无头浏览器实测 /chart — 修复前 pageerror「Bar series item data value of high
  must be a number」+ root 空；修复后页面完整渲染（11 canvas），console/pageerror 全零，振荡器
  切换（无/RSI/KDJ/MACD）与周期切换均无错误；前端 lint + build 通过（产物同步）。

# Changelog

AI 维护者每次收工时按「收工仪式」（AGENTS.md §6）在此追加条目。

## 2026-08-20 — 数据源中文名 + 东财 https 自动降级 + Yahoo 美股第二源

- **数据源中文名（括号英文名）**（commit 76948f7）：`/settings` 页与配置 API 显示
  东方财富 (eastmoney) / 腾讯行情 (tencent) / 同花顺 (ths) / 东方财富延时 / BaoStock /
  AkShare / Tushare / Finnhub / Yahoo Finance。
- **东财 https 优先自动降级**（commit 2170ff2）：`_em_get` https 优先，TLS 被重置时自动降级 http。
  用户确认当初根因是 Clash 虚拟网卡（TUN/fake-IP）——安全债消除：网络正常自动走加密通道，
  Clash TUN 干扰时自动降级，行情不依赖单协议（见 `.scratch/eastmoney-proxy/` 结论更新）。
- **Yahoo Finance 美股第二源**（commit 2170ff2）：`_get_yahoo_quote`（chart API，免费无 key），
  美股链 Finnhub → Yahoo → None；实测 AAPL 311.72/52w 高 344.57，NVDA 在 Finnhub 不可用时
  自动切 Yahoo。
- 测试：test_data_fetcher 新增 em_get 双分支 + Yahoo 解析用例；全量回归 **168 passed**；
  前端 lint + build 通过（产物同步）。

## 2026-08-20 — 数据源选择 + 移除全部 Demo 假数据

- **数据源选择**（commit 0769eb7）：`/settings` 页可对「实时行情 / 因子 / K线」三个数据域
  选「自动」或钉住某个源（如实时行情选腾讯）；钉住的源排到链首优先尝试，失败仍自动降级。
  后端 `datasource_config`（settings 表持久化）+ `GET/PUT /api/quant/datasource/config`。
  实测：钉住 tencent → source=tencent；auto → 东财优先。
- **移除全部 demo 假数据**（commit a830b2a）：删 `DEMO_DATA` / `MockFactorSource` /
  `_dynamic_demo_price` / monitor demo 守卫；所有数据源失败时**如实返回 None/空**，
  不再出现假数据。因子行业列表改查真实数据。模拟交易「无真实行情拒绝成交」。
- 测试：test_datasource_config 3/3（新增）+ test_data_fetcher 实时源排序用例；
  全量回归 **168 passed**；前端 lint + build 通过（产物同步）。
- 影响说明：若某市场所有源均不可用，页面将显示无数据/报错（不再显示假数据）；
  可在 `/settings` 手动选择偏好的源。

## 2026-08-20 — 同花顺四连：K线源 / 财务指标 / 异动归因 / 公司行为

- **K 线源**（`THSKlineSource`，commit 3f227d8）：A股日线官方数据 + 周/月线由日线重采样，
  进 CN 链首位（THS→AkShare→BaoStock→东财），修复 push2his 被风控导致的图表页不可用。
  实测茅台 1d 255 根 / 1w 55 / 1mo 13。
- **财务指标 enrichment**（commit 6588bbd）：`ths_indicators` 缓存表 + `refresh_indicators`
  （报告期未变不重拉）+ `enrich_universe_df` 接入因子刷新——监控股票
  ROE/ROA/毛利率/净利率/负债率/营收利润增速入因子库（20 只 CN 监控股实测）；
  修复 daily_metrics INSERT 硬编码 net_margin/debt_ratio 为 None 的旧问题。
- **异动归因**（commit 7ffc199）：`quant_anomalies` 表 + 当日全市场官方异动原因入库
  （涨停/跌停/大涨/大跌/快速拉升/下挫），简报新增「今日异动归因（同花顺）」小节。
- **事件日历增强**（commit d889fde）：THS 公司行为（分红/送股，监控股票）并入事件日历，
  Tushare 无配额时仍可用；实测 2026 年监控股票 25 笔分红。
- 测试：新增/更新单测全过（ths_source 8 + ths_service 5 + events 3 + briefing 6）；
  全量回归 pytest backend/tests/。
- 限流：文档未公开；实测当天累计 ~100 次调用全部正常。设计保守：批量 + 按需 + 缓存。
- API 新增：`/api/quant/ths/indicators`（GET/POST refresh）、`/api/quant/ths/anomalies`（GET/POST refresh）。

## 2026-08-20 — 同花顺数据源激活：官方估值因子全量上线 + 财务指标可用

- 用户提供 `THS_API_KEY`（fuyao.aicubes.cn，同花顺官方）并写入 `backend/.env`。
- 真实验证通过：
  - `valuations/snapshot` 批量估值：茅台 PE-TTM 19.54/PB 6.33、平安 PE 5.09/PB 0.47，
    与东财延时源交叉一致（官方数据确认）；
  - `financials/indicators` 财务指标：茅台毛利率 89.76%/ROE 10.57、宁德 ROE 12.08/
    毛利率 23.93、平安负债率 90.98（roe/roa/gross_margin/net_margin/debt_ratio 映射就绪）。
- `refresh_universe()` 全市场刷新：**THS 估值源赢得降级链**（Tushare 日配额仍耗尽），
  5549 只全量、16645 因子行入库（pe_ttm/pe_mrq/pb/ps_ttm/pcf_ttm），daily_metrics 带名称。
- 修正：估值字段 `pb_mrq` 映射、`latest_report` 按披露日历 + `financial_indicators_latest`
  自动回退上一期（当期未披露 5003 时）、THS df 补 name。
- 测试：`test_ths_source` 7/7；全量回归 157 passed。
- 提交：`92f78a8`（骨架）+ 本次修正提交。
- 下一步：财务指标按需 enrichment（监控列表/选股候选 Top N 补 ROE/毛利率/增速），
  事件/日历/异动归因接入。

## 2026-08-20 — 东财延时因子源：真实因子数据全量落地（5552 只）

- 调研发现 `push2delay.eastmoney.com`（延时 15 分钟）与 push2 同构但不被风控，
  clist 提供全 A 股 PE(动)/PE-TTM/PB/ROE/换手率/市值/行业。
- 新增 `EastMoneyDelayFactorSource` 接入降级链：Tushare → **东财延时** → BaoStock → AkShare → Mock。
- 修复两处：
  1. `refresh_universe` 只认「含因子列的 df」为源成功——Tushare 限流回退的"空壳 universe"
     不再阻断降级链（此前导致东财延时源永远轮不到）；
  2. clist 分页：单页上限 100 + 后段页偶发超时 → 每页重试 3 次。
- **真实数据验证**：`refresh_universe()` → 21205 因子行；turnover_rate 5552 只完整、
  pe_ttm/pb/roe 5215+ 只；抽查茅台 PE 19.54 / PB 6.33 / ROE 16.75、平安银行 PE 5.09 / PB 0.47。
- 清理：删除失败刷新遗留的 5547 行全空 daily_metrics 占位（daily_metrics 现为 5552 行真实数据）。
- 测试：`test_eastmoney_delay_source` 2/2（新增）+ 既有 11 个新测试全过（13 passed）。
- 提交：`a0ab7e1`…`d14b132` 之后新增本功能提交（见 git log）。
- 未决：财务深数据（毛利率/营收增速等）仍需 Tushare 积分升级或 BaoStock 网络恢复。

## 2026-08-19 — Tushare 真数据接入 + 事件日历 + 策略模板 + 模拟交易

- **Tushare 接入**（用户提供 token）：`TUSHARE_TOKEN` 已写入 `backend/.env`（gitignored，不入库）。
  因子管线新增**双级缓存**（`ts_universe_cache` / `ts_daily_cache`）——免费档 `stock_basic`/`daily_basic`
  限 1 次/小时，首次成功后落库、限流自动回退，避免刷新掉进 Mock 假数据。
  ⚠️ 实测发现该档位完整限制为 **1次/分钟 + 1次/小时 + 5次/天**（失败的调用同样计入窗口）；
  当日配额耗尽后须等北京时间次日 0 点重置。建议升级 200 积分（免费实名）解除瓶颈。
- **事件日历**：Tushare 分红送转（除权日）+ 限售解禁（解禁日）→ `quant_events` 表；
  API `GET /api/quant/events` + `POST /refresh`；前端 `/events` 页（区间 + 类型筛选）。
- **策略模板**：4 个预配置回测模板（低估值红利 / 双均线趋势 / 动量优选 / 等权一篮子），
  回测页一键套用；API `GET /api/quant/backtest/templates`。
- **模拟交易 Paper Trading**：真实行情成交的模拟组合（买卖/现金校验/实现盈亏/净值重估，
  demo 假数据拒绝成交）；`/api/quant/paper` CRUD + trade + mark；前端 `/paper` 页。
- 测试：`test_factor_source` 3/3、`test_events_service` 2/2、`test_strategy_templates` 3/3、
  `test_paper_service` 3/3 全过；前端 lint + build 通过（产物同步）。
- 提交：`0b77b79`(因子缓存) / `b0e151c`+`73d696d`(事件日历) / `89b1b8c`(策略模板) / `bd45b1a`(模拟交易)。
- 未决（需人看）：
  1. Tushare 积分档偏低——`stock_basic`/`daily_basic` 限 1 次/小时；`fina_indicator`/`income`/
     `disclosure_date`/`forecast` 无权限（成长/质量因子、财报披露、业绩预告暂缺，升级积分可解锁）。
  2. `LLM_API_KEY` 未配置——每日简报走模板模式；新闻归因（issue 03）依赖 LLM key。
  3. 真实因子刷新已安排后台验证（配额重置后自动跑，结果待确认）。

## 2026-08-19 — CN/HK 行情多源降级（东财→腾讯）

- 背景：东财 `push2/push2his` 实时行情接口被服务端秒断（见 `.scratch/eastmoney-proxy/PRD.md`），
  行情长期回退 demo 假数据。
- 新功能：`data_fetcher.py` 给 CN/HK 加腾讯行情源作降级——东财失败自动切腾讯
  （`qt.gtimg.cn` 实时报价 GBK 解析 + `web.ifzq.gtimg.cn` 日 K 320 根算 52 周高低点），
  都失败才回退 demo。`source` 字段区分 eastmoney/tencent/demo。
- 修正：实现中曾误用腾讯周 K（会算出约 6 年高低点），改为日 K 对齐东财 ~1.2 年窗口。
- 效果：实测 600519/000001/00700/01810 均 `source=tencent` 拿到真实行情；不再依赖 Clash 对
  东财域名的规则，也基本免疫 push2 风控。
- 测试：`test_data_fetcher.py` ALL PASSED（新增 `_tencent_secid` 纯函数 + 东财失败降级腾讯用例），
  `test_briefing` 6/6、`test_price_history` 6/6。
- 提交：`323215d`(feat) + `aac1f90`(docs 东财 issue 更新)。

## 2026-08-18 — 清理 + 简报趋势图 + 东财连通性根因

- **A 数据清理**：备份 `data/sentinel.db`（`.bak` 已加 `.gitignore`）后，清空量化测试写入真实库的残留
  —— `portfolios` 64 / `portfolio_holdings` 142 / `factor_values` 23118 / `daily_metrics` 9396（全是
  pytest 的 Mock 因子刷新与组合 CRUD 产物，无真实使用痕迹），VACUUM 后库从 5.12MB 缩到 929KB；
  v0.2.0 真实数据（stocks/alerts/briefings/price_history/snapshots）原样保留。
- **B 简报内嵌回撤趋势图**（`.scratch/briefing-trend/`）：后端 `BriefingGenerator._load_trends` 读
  `price_history` 近 30 天回撤序列写入 `briefings.stats.trends`（不进 LLM 上下文省 token，以简报日期为
  窗口基准）；前端 `BriefingModal` 复用 `Sparkline` 渲染「📉 回撤趋势」小节（恶化标红/改善标绿，无数据不出现）。
- **C 东财连通性根因**（`.scratch/eastmoney-proxy/PRD.md`，ready-for-human）：本机 Clash Party（mihomo）
  TUN/fake-IP 模式把 `push2.eastmoney.com`/`push2his` 解析到 198.18.0.x 假 IP，代理路由规则损坏导致
  https 重置/http 502；`data_fetcher.py` 的 http 降级是治标 workaround。修复方向：Clash 加
  `DOMAIN-SUFFIX,eastmoney.com,DIRECT` 规则，修好后 URL 可回 https。
- 提交：`a0ab7e1`(fix 数据源遗留改动入库) / `dee9fa7`+`291d943`(feat 简报趋势图) / `bafee18`+`e1718e8`(chore/docs)。
- 验证：`test_briefing.py` 6/6（含新增趋势用例）、`test_price_history.py` 6/6、`test_data_fetcher.py` ALL PASSED；
  pytest 137 passed；前端 lint + build 通过。
- 未决：并行会话的 `backend/tests/quant_engine/conftest.py`（临时 DB 隔离）+ `test_api.py`（test_db_isolation）
  尚未合入（非本 session 产物，未动）；Clash 东财规则需人工改（见 C）；东财 http 安全债待规则修好后回 https。

## 2026-08-15 — 与 GitHub 合并：量化分析平台（v1.0）入库

- 同步远端 20 个提交：合并 `origin/main`（本地 +10 提交、远端 +20 提交，分叉点 2026-05-16）。
  解决 4 处冲突：`AGENTS.md`（本地操作手册 × 远端协作指南合并）、`CLAUDE.md`（Backend 架构段合并，
  保留量化分层 + 本地 briefing/price_history 描述）、`backend/main.py`（保留双方 import）、
  `backend/static/index.html`（取远端，随后重新 build 覆盖）。
- 入库内容：`backend/quant_engine/` 全套（M0-M6：K 线 / 指标 / 因子选股 / 回测 / 组合 / 风险，
  数据源 AkShare / BaoStock / 东财 / Finnhub）、前端 6 页面 + react-router、
  `backend/tests/quant_engine/`（137 测试）、USER_GUIDE / README / quant-roadmap / ADR 文档。
- 修复 `fix(quant)`：BaoStock login 无超时——其 `send_msg` 是 `while: recv` 循环，
  网络代理断连（recv 返回 b''）时无限空转，因子刷新/测试挂 68s+；改为 daemon 线程 + 10s 超时，
  fallback 链 12.5s 内完成。验证：pytest 137/137 通过、`test_data_fetcher.py` 全过、
  前端 lint 0 警告 + build 通过。
- 未决：工作区 `data_fetcher.py`/`monitor.py` 未提交改动（日志/HTTP 直连/demo 防覆盖）未纳入提交；
  本机 akshare 因 openpyxl 版本（3.0.10 < 3.1.0）降级不可用，因子数据走 Mock fallback；
  尚未推送合并结果到 GitHub（需用户确认）。

## 2025-08-14 — 基础设施：AI 主导模式起步

- 新增 `AGENTS.md`：AI 维护者操作手册（开工仪式 / 工作循环 / 升级规则 / 收工仪式），
  由 DSH `dsh-agent-instructions` 自动注入每次会话。
- 新增 DSH agent preset `stock-sentinel`：AI 维护者 persona（模式 B：AI 自主干，人看结果）。
- 说明：本条目由人工主导的转换会话记录，作为 CHANGELOG 格式的样例。

## 2026-08-14 — 每日简报（Daily Briefing）

- 新功能：每日定时生成中文简报，聚合监控组合状态（市场分布 / 回撤 Top / 超阈值清单 / 今日异动 / 昨今对比），
  支持 LLM 生成（OpenAI 兼容接口，`.env` 配置 `LLM_API_KEY` 等）与无 Key 模板兜底。
- 新增 `backend/briefing.py`：`BriefingGenerator`（快照采集 → 上下文组装 → LLM/模板生成 → 落库）+ `BriefingScheduler`（daemon 线程，默认北京时间 08:30 触发，每天一条）。
- 数据库新增 `stock_snapshots`（每日快照，供对比）与 `briefings`（简报记录，每天一条 REPLACE）两张表。
- 新 API：`GET /api/briefings/`、`GET /api/briefings/latest`、`GET /api/briefings/{id}`、`POST /api/briefings/generate`。
- 前端：Dashboard 新增「📰 简报」入口 + `frontend/src/components/BriefingModal.jsx`（轻量 markdown 渲染、历史切换、手动生成）。
- 修复：`/api/alerts/*` 被 catch-all 静态路由遮蔽导致一直返回 HTML 的既有 bug（Alert API 移至静态托管之前）。
- 测试：新增 `backend/test_briefing.py`（5/5 通过，临时 DB 隔离）。
- 验证：模板简报已对真实库生成成功（mode=template）；前端 build 通过。
- 未决：`backend/test_data_fetcher.py` 的 demo 断言因东财 API 可达而过时（既有问题，非本次引入）；
  `data_fetcher.py`/`monitor.py` 的未提交改动（直连/日志）未纳入本次提交。

## 2026-08-14 — 历史行情落库与回撤趋势（Price History）

- 新功能：每次刷新拿到真实行情时写入 `price_history`（15 分钟时间桶幂等，demo 回退不落库，
  保留 90 天可配 `PRICE_HISTORY_RETENTION_DAYS`），Dashboard 新增「趋势」列展示近 30 天回撤 sparkline（纯 SVG，无新依赖）。
- 数据库新增 `price_history` 表（`UNIQUE(ticker, bucket)` + ticker 索引）。
- 新 API：`GET /api/history/{ticker}?days=30`（无数据返回 200 + 空数组，`days` 上限 90）。
- 前端：新增 `frontend/src/components/Sparkline.jsx`；Dashboard 首次加载与全量刷新后拉取历史。
- 修复：`backend/test_data_fetcher.py` 的 demo 断言改为确定性 mock（屏蔽真实 API 验证回退路径），东财可达时不再误红。
- 修复：前端基线遗留的 3 处 `react-hooks/preserve-manual-memoization` lint 错误（三个 fetch* 回调补 setter deps）。
- 清理：issue tracker 过时状态——`alert-notification` 01/02/03 与 `daily-briefing` SPEC 标 `done`；
  triage 词汇表新增 `done` 标签（`docs/agents/triage-labels.md`）。
- 测试：新增 `backend/test_price_history.py`（6/6 通过，临时 DB 隔离）；`test_data_fetcher.py` 与 `test_briefing.py` 全量回归通过；前端 lint + build 通过。
- 提交：`fix`(test_data_fetcher) / `chore`(tracker 清理) / `feat`(历史行情后端+API) / `feat`(前端 sparkline) 共 4 笔，小步分离。
- 未决（需人看）：`backend/data_fetcher.py`、`backend/monitor.py` 的未提交改动仍保持原样未纳入提交（其中东财 URL https→http 降级属安全隐患，建议人工确认）；
  历史行情需真实 API 运行一段时间才有趋势数据，sparkline 初期多为"暂无趋势"占位。
## 2026-08-28 — 修复股票监控新增股票

- 新增接口现在识别监控页提示的代码格式：A 股 `600519.SS/.SH/.SZ` 自动存为 `600519`，港股 `700.HK`/`0700.HK` 自动补齐并存为 `00700`；由此避免 A 股误按美股请求行情。
- `POST /api/stocks/` 支持可选 `name`，用户手填名称将作为监控项显示名；同一股票的后缀写法与规范代码会正确判重。空代码或格式不合法的 A 股/港股后缀返回 422，避免写入无效项。
- 新增 `backend/test_stock_management.py`（6 个临时 SQLite API 回归测试），不访问外部行情、不读写真实 `data/sentinel.db`。
- 验证：`python backend/test_data_fetcher.py`、`python -m pytest backend/test_*.py -q`（25 passed）、`python -m pytest backend/tests/ -q`（232 passed，1 条既有运行时 warning）、前端 lint + build 通过。
- 与「优化首页股票监控模块」会话隔离：未修改 `frontend/src/pages/Dashboard.jsx` 或首页样式。
## 2026-08-28 — 名称优先新增股票与跨市场选择

- 新增股票弹窗改为只输入公司名称（支持名称/拼音搜索），候选项显示名称、代码与市场；普通候选点选后即以默认设置加入监控，不再要求填写代码、名称或提醒阈值。
- 同名候选覆盖多个市场时，弹窗要求显式选择范围：可只选一个、勾选多个，或一键全选，默认只勾选用户先点击的市场，避免误监控。
- 新增 `AddStockModal` 与跨市场候选分组测试；Dashboard 只保留弹窗入口接线，未修改首页监控表格、筛选、统计或布局。
- 测试隔离：`test_factors_refresh` 改为 mock 路由绑定的 `refresh_universe`，只验证 API 合约，不再因真实全市场数据源与代理网络卡住。
- 验证：`node --test src/lib/stockSearch.test.js`、前端 lint/build、`python backend/test_data_fetcher.py`、根目录后端测试 25 passed、量化测试 232 passed（1 条既有零初始资金 RuntimeWarning）。

## 2026-08-28 — 首页股票监控：可解释的多周期回撤

- 回撤统一为 3 个月、6 个月和 1 年滚动日历窗口，返回区间起点、截至日、最高/最低价及日期、回撤和距低点；A/港/美股使用同一计算函数，历史覆盖不足时明确返回 `数据不足`。
- 数据库给 `stocks` 和 `price_history` 新增 `drawdown_windows` JSON 快照；`GET /api/history/{ticker}` 支持 `window=3m|6m|1y`，旧历史记录不再伪装成新窗口趋势。既有 52 周字段固定映射到 1 年，告警、简报与历史语义保持稳定。
- 首页新增记忆型 3 月/6 月/1 年选择器，概览、排序、表格、趋势、CSV 同步切换；用公式、区间高点日期、实际行情时刻和「数据不足」解释指标。提醒列明确固定 1 年且仅按用户自己的阈值标出「已越线/关注」，不再使用隐藏的 -10%/-20% 色阶。
- 体验：补齐加载失败、空自选股、筛选无结果、键盘焦点和窄屏可读性（核心列保持可读并支持横向查看）。
- 设计决策：新增 `docs/adr/0003-monitoring-drawdown-windows.md`；实施记录见 `.scratch/dashboard-monitoring/`。
