# ADR-0001: 量化引擎架构

> 状态: ✅ 已采纳
> 日期: 2026-06-02 (M0 阶段)
> 决策者: 项目所有者 + AI 协作

---

## 背景

v0.2.0 项目只有"监控+告警"功能。要升级到"对标世界领先水平的量化分析平台"，需要新增大量功能：K 线图表、技术指标、多因子选股、回测引擎、组合管理、风险分析。

---

## 决策

**新建独立模块 `backend/quant_engine/`**，与 v0.2.0 的 monitor / alerter / data_fetcher 完全解耦。

### 目录结构
```
quant_engine/
├── 核心 (纯函数 + dataclass)
│   ├── indicators.py    # 13 技术指标
│   ├── factors.py       # 15 因子
│   ├── backtest.py      # 事件驱动回测引擎
│   ├── portfolio.py     # 组合 CRUD
│   └── risk.py          # 13 风险指标
├── 服务 (业务编排)
│   ├── kline_service.py
│   ├── backtest_service.py
│   ├── factor_service.py
│   └── portfolio_service.py
├── 数据源抽象
│   └── data_source/
│       ├── eastmoney_source.py
│       ├── akshare_source.py
│       ├── finnhub_source.py
│       └── factor_source.py
└── API 路由
    └── api/
```

### 关键设计
1. **纯函数优先**（指标/因子）—— 方便测试和组合
2. **dataclass** 用于有状态对象（Trade / BacktestResult）
3. **服务层薄** —— 业务逻辑放在核心模块
4. **API 薄** —— 只做参数校验 + 调用服务

---

## 备选方案

### 方案 A: 集成到现有模块
直接把量化代码加到 `monitor.py` / `data_fetcher.py`。

**否决理由**：
- 模块职责混乱，监控和回测不应混在一起
- 测试困难（没有清晰边界）
- 未来如果用户放弃 v1.0，quant_engine 难整模块移植

### 方案 B: 引入第三方库（Backtrader / Zipline / Lean）
**否决理由**：
- Backtrader 接口死板，A 股涨跌停/T+1 难定制
- Zipline 已停更
- Lean 是 C# + Python 混合，重
- 自研工作量 1-2 周（与集成第三方时间相当），**长期更灵活**

### 方案 C: 全新微服务
把 quant_engine 拆成独立 service + DB。

**否决理由**：
- 单用户工具，无需分布式
- 1 人维护，微服务增加复杂度
- 性能充裕（事件驱动 + SQLite + 5 年数据 < 1s）

---

## 后果

### 好的
- ✅ 模块边界清晰，单测容易写（M6 一下午 137 个测试）
- ✅ 删 v0.2.0 模块不影响 quant_engine
- ✅ 文档 / 架构 / 测试 各管各的
- ✅ 未来升级 Tier 2/3 时不重构

### 代价
- ⚠️ 新增 10+ 文件（M0 一开始就有 12 个）
- ⚠️ 文档要写 2 份（CLAUDE.md 覆盖 v0.2.0 + v1.0）

---

## 经验

- **新功能先建独立模块**，不要塞进旧模块
- **纯函数 + dataclass** 是量化代码的最佳搭配
- **单测必须** —— M6 写测试发现 5 个真 bug
