# PRD: 模拟交易（Paper Trading）

Status: done
Owner: agent
Version: 1.0
Date: 2026-08-19

## 概述

以**真实行情**成交的模拟组合：建仓/平仓、现金与持仓校验、实现盈亏、
mark-to-market 净值重估与净值曲线。demo 假数据拒绝成交。

## 实现

- 后端：`paper_portfolios` / `paper_positions` / `paper_trades` / `paper_equity` 四表；
  `quant_engine/paper_service.py`（create/close/delete/trade/mark/get_detail）；
  API `/api/quant/paper` CRUD + `/trade` + `/mark`。
- 前端：`/paper` 页面（组合列表 + 创建 + 持仓/成交表 + 下单表单 + 重估净值）。
- 测试：`test_paper_service.py` 3/3（mock 行情价格）。

## Todo

- [x] 后端 + 测试（commit bd45b1a）
- [x] 前端页面 + 路由（commit bd45b1a）

## 后续

- 按策略信号自动交易（对接 backtest 信号引擎）；组合净值曲线图表；每日自动 mark。
