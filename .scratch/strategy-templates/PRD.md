# PRD: 策略模板（Strategy Templates）

Status: done
Owner: agent
Version: 1.0
Date: 2026-08-19

## 概述

预配置 4 个可复用回测模板（低估值红利 / 双均线趋势 / 动量优选 / 等权一篮子），
回测页一键套用（策略 + 参数 + 建议标的 + 再平衡频率），可再手动调整。

## 实现

- `quant_engine/strategy_templates.py`：TEMPLATES 静态数据 + get_templates。
- API：`GET /api/quant/backtest/templates`。
- 前端：Backtest 页顶部模板卡片，点击填充表单。
- 测试：`test_strategy_templates.py` 3/3（结构校验 + API 冒烟）。

## Todo

- [x] 后端模板 + API + 测试（commit 89b1b8c）
- [x] 前端模板选择（commit 89b1b8c）
