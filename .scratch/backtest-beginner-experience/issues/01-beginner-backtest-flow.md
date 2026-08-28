# 01: 新手回测流程与名称选股

Status: done
Priority: P1

## Scope

重构 `frontend/src/pages/Backtest.jsx` 的输入工作流，复用量化搜索 API，以名称联想和股票标签替换代码文本框。新增无依赖的前端流程单测，确保模式映射、去重、市场校验与提交 payload 可回归验证。

## Done When

- PRD 的验收条件全部满足。
- `node --test frontend/src/lib/backtest-flow.test.js`、`npm run lint`、`npm run build` 通过。
- 回测页在浏览器中验证单股、组合和搜索选择流程。

## Comments

- 2026-08-27：复用现有搜索 API，新增 5 个前端流程单测。浏览器验证名称搜索、组合最少两只提示、直接代码回车添加和高级设置。没有修改回测 API 或计算语义。
