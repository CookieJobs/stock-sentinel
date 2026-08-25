# Issue 02: AI 策略选股 — 前端（Screener 重构：策略卡 + AI 生成 + 高级模式）

Status: done

## What to build

重构 `frontend/src/pages/Screener.jsx`（+ `lib/api.js` 加 screener 三个端点封装）：

1. **模式切换**：「✨ AI 策略选股（推荐新手）」默认 / 「⚙️ 手动高级模式」（保留现有
   筛选条件 UI，折叠可见）。
2. **策略卡网格**：emoji + 名字 + tagline + 适用人群 + 风险标签 + 条件 chips
   （如「PE ≤ 25」）；点「用这个策略选股」一键执行并展示结果；卡片可展开，逐条
   显示条件的大白话解释 + 排名方式 + 为什么这样选。
3. **AI 生成策略**：自然语言输入框 + 「🤖 AI 生成策略」按钮 → 生成的新策略卡插入
   网格顶部（带「AI 生成」徽标）→ 点击执行。
4. **结果表**：沿用现有表；有 `skipped_factors` 时黄色提示「以下条件暂无数据已跳过」；
   ROE/毛利率显示归一化（`>1` 视为百分比原值，否则 ×100）。
5. **因子说明区**：展示 `description_zh` 白话 + 单位。

## Acceptance criteria

- [ ] 默认进入 AI 策略模式，策略卡可一键选股并出结果
- [ ] 手动高级模式保留原有全部功能（筛选/排名/TopN/刷新/因子说明）
- [ ] 无 LLM Key 时 AI 生成按钮给出友好中文提示，内置策略不受影响
- [ ] 结果表 ROE/毛利率显示正确（兼容百分比/小数两种存储）
- [ ] `npm run lint && npm run build` 通过，产物同步提交

## Blocked by

- `01-screener-backend`（API 先就绪）

## Comments

- 2026-08-26：PRD `.scratch/ai-strategy-screener/PRD.md` 已就绪。
- 2026-08-26：完成（commit c890b83）。双模式默认 AI 策略；策略卡 + 展开白话说明；
  自然语言生成插卡；手动高级模式保留；结果 ROE/毛利率归一化显示；指标小词典白话版。
  lint + build 通过，产物同步。
