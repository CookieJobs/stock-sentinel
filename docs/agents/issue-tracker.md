# Issue Tracker — 如何记 issue

> 给 AI 记 issue 时的**格式规范**。

---

## 🎯 何时记 issue

- 发现 bug 但没立即修
- 发现可改进但当前不是 P0
- 用户提的需求但当前没排期
- 第三方依赖的版本升级提醒

**不记**：
- 当下立即 commit 修掉的 bug（写到 commit message 即可）
- 一次性的小事（不值得追）

---

## 📁 文件位置

`.claude/ISSUES.md`（**未实现**——v1.0 没用上 issue tracker，用 `TODO.md` 就够了）

如果未来 issue 多到 TODO 不够用，**再启用** `.claude/ISSUES.md`，格式参考下面。

---

## 📝 Issue 格式（未来用）

```markdown
## ISSUE-001: 回测引擎 factor_rank 排名方向错

**状态**: ✅ 已修复 (commit 48e1d52)
**优先级**: P0
**发现时间**: 2026-06-03 (M6 打磨时)
**发现者**: 单测 test_signal_factor_rank_volatility 失败

### 现象
volatility 因子 (desc=越小越好) 选了**最大**波动率的票。

### 根因
backtest.py signal_factor_rank 用 nlargest 固定选最大，没看 meta['direction']。

### 修法
按 `meta['direction']` 选 nlargest/nsmallest。

### 教训
desc 方向因子必须看 direction 字段，不能默认 nlargest。
```

---

## 🏷️ 当前用的标签（triage-labels.md 里有）

| 标签 | 含义 |
|----|----|
| `needs-triage` | 刚提，还没分类 |
| `needs-info` | 信息不够，要追问 |
| `ready-for-agent` | 明确，AI 可直接动手 |
| `ready-for-human` | 需用户决策 |
| `wontfix` | 不修（说明原因）|

**v1.0 实际**：项目里 issue 几乎都在 `TODO.md` 里跟踪，没用 issue 跟踪系统。**Mavis 也倾向于用 TODO 而不是建 issue**——轻量。

---

## 🎯 何时升级到完整 issue 系统

- 单人项目：**TODO.md + .claude/ISSUES.md** 够用
- 多人项目 / 长期演进：考虑用 GitHub Issues / Linear
- v1.0-MVP 阶段：**不需要**

---

## 🆘 接手 AI

发现 bug 不知道该不该记时：
1. 简单 bug（< 30 分钟修）→ 立即修，commit message 写明
2. 复杂 bug（> 30 分钟）→ 在 `TODO.md` 加一行
3. 战略性需求 → 在 `TODO.md` 加 P1/P2 段
