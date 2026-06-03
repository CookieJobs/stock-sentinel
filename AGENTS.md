# AGENTS.md — AI 协作指南

> **给所有 AI 助手**（Claude Code / Mavis / Codex / Cursor / 其他）。
> 第一次接手这个项目时，**先看 CONTEXT.md，再看这个**。

---

## 🎯 你的目标

帮项目所有者**继续完善个人投研型量化分析平台**：
- ✅ **可以改**：新功能 / 修 bug / 重构 / 加测试
- ⚠️ **改前确认**：改 schema / 删文件 / 改环境配置
- ❌ **不要碰**：生产数据（除非用户明确说）

---

## 📋 接手清单（5 分钟）

```
[ ] 读 CONTEXT.md（30 秒）
[ ] 读 CLAUDE.md 的"Architecture"段（10 分钟）
[ ] 读 .claude/PROJECT_HISTORY.md 的"教训"段（5 分钟）
[ ] 跑 ./start.sh，浏览器把 6 页面点一遍
[ ] 跑 pytest backend/tests/quant_engine/ -q 确认 137 都过
[ ] 读 .claude/TODO.md 选下一个活
```

完成 6 步后，**你就是这个项目的合格协作者**。

---

## 🛠️ 必读

| 文件 | 用途 | 必读度 |
|----|----|----|
| `CONTEXT.md` | 30 秒项目快照 | ⭐⭐⭐⭐⭐ |
| `CLAUDE.md` | 架构 + API + 命令 | ⭐⭐⭐⭐⭐ |
| `.claude/PROJECT_HISTORY.md` | 开发历程 + 教训 | ⭐⭐⭐⭐ |
| `.claude/TODO.md` | 当前待办 | ⭐⭐⭐⭐ |
| `docs/quant-roadmap.md` | 完整路线图 | ⭐⭐⭐ |
| `docs/adr/0001-*.md` | 架构决策 | ⭐⭐ |
| `docs/adr/0002-*.md` | 数据源决策 | ⭐⭐ |
| `README.md` | 用户视角 | ⭐ |

---

## ⚙️ 工作规范（违反会炸）

### 1. Worktree 模式（最严）
**所有代码改动必须在 worktree 里**。main checkout 是参考基线，永远干净。

```bash
# 错误（直接改 main）
cd /Users/liujin/Documents/myCraft/stock-sentinel
vim backend/main.py  # ❌

# 正确
git worktree add .worktrees/feat-xxx -b feature/xxx origin/main
cd .worktrees/feat-xxx
vim backend/main.py  # ✅
# 改完跑测试 → commit → push → PR
```

**为什么**：watch-mode dev server 不会被打断、main 永远可回退。

### 2. Commit 前必跑
```bash
# 后端
.venv/bin/python -m pytest backend/tests/quant_engine/ -q
# 前端
cd frontend && npm run lint && npm run build
```

**任何一项失败都不准 commit**。

### 3. Commit message 用中文 + 详细
**用户明确要求**（CLAUDE.md / M1 起所有 commit 都是中文）：
- ✅ 好的：`feat(quant): 加 BaoStock 源 + A 股 5 年 K 线 (2.6s 拉 1212 行)`
- ❌ 差的：`add baostock source`

格式参考：`<type>(<scope>): <subject> + <body>`

`<type>`：feat / fix / refactor / test / docs / chore
`<scope>`：quant / data / api / ui ...
`<body>`：为什么 + 改了什么 + 测试结果

### 4. 量化引擎代码风格
- **纯函数优先**（指标/因子）
- **dataclass** 用于状态（Trade / BacktestResult / TradeRecord）
- **pd.Series → pd.Series**（指标）
- **pd.DataFrame** 用于批量回测
- **错误用 ValueError**（业务）+ **HTTPException**（API）
- **不在指标函数里 print/log**（纯函数，干净）

### 5. 测试规范
- 每个新指标/因子/函数**必须有单测**
- API endpoint 必有 TestClient 集成测试
- happy path + 边界 + 错误都覆盖
- **修复 bug 时先写一个失败的测试**（TDD 风格）

---

## 🚫 不要做

1. ❌ 在 main checkout 改代码（违反 worktree 规则）
2. ❌ 不跑测试就 commit
3. ❌ commit `__pycache__/` `node_modules/` `data/sentinel.db` `.env`（已在 .gitignore，但别强推）
4. ❌ 删别人写好的测试（除非确认是过时）
5. ❌ 在指标函数里加 print 调试（用 logger）
6. ❌ 调外部 API 不加 try/except（数据源不稳，必加）
7. ❌ 单个 commit 超过 500 行改动（拆小）
8. ❌ 不写 commit message（"update" 这种空消息被项目规则禁止）

---

## 🎯 决策原则

**遇到不清楚的决策时**：

1. **先查文档** —— `.claude/PROJECT_HISTORY.md` / ADR / 已有代码
2. **再做选择** —— 项目风格倾向（参考 CLAUDE.md）
3. **不确定就问用户** —— 不要"自主决定"大方向

**对当前用户（投资人 / 节奏快）的偏好**：
- 喜欢**直接给方案 + 执行**，不绕弯
- 接受**激进砍范围**（v1 简化是常态，不是 bug）
- 重视**"能立刻用"** > "架构完美"
- 关注**回测/选股/组合** 这些核心场景

---

## 🔧 常见任务模板

### 加一个新指标
```python
# 1. 在 backend/quant_engine/indicators.py 加函数（纯 pd.Series → pd.Series）
def NEW_INDICATOR(close, period=14):
    return close.rolling(period).mean()

# 2. 在 INDICATORS 注册表加
"NEW_INDICATOR": {"fn": NEW_INDICATOR, "params": {"period": 14}, "inputs": ["close"]},

# 3. 在 OSCILLATOR_INDICATORS 加（如适用）
# 4. 在 tests/quant_engine/test_indicators.py 加测试
def test_new_indicator_xxx():
    ...

# 5. 跑 pytest 确认过
# 6. commit
```

### 加一个新数据源
```python
# 1. 在 backend/quant_engine/data_source/ 加新文件
class NewSource(DataSourceBase):
    name = "newsource"
    def get_kline(self, ticker, market, period, start, end, adj):
        # 返回 pd.DataFrame(columns=trade_date, open, high, low, close, volume, amount)
        ...

# 2. 在 __init__.py 的 SOURCES 列表加（按优先级）
SOURCES = [TushareFactorSource, NewSource, AkShareFactorSource, MockFactorSource]

# 3. 加测试
# 4. commit
```

### 修一个 bug
```
1. 写一个失败的测试（重现 bug）
2. 跑测试确认失败
3. 改代码
4. 跑测试确认过
5. 跑全套测试确认没破坏其他
6. commit（message 写明"bug 在哪 + 怎么修 + 测试覆盖"）
```

---

## 📡 监控进度

```bash
# 看最近的 commit
git log --oneline -10

# 看所有 worktree
git worktree list

# 跑完整测试 + lint + build
.venv/bin/python -m pytest backend/tests/quant_engine/ -q
cd frontend && npm run lint && npm run build
```

---

## 🆘 卡住时

1. 看 `.claude/PROJECT_HISTORY.md` 的"教训"段 —— 前人踩过的坑
2. 看 `docs/adr/` —— 关键架构决策的理由
3. 跑测试看错误 —— 95% 的 bug 测试会告诉你
4. 问用户 —— 决策类问题别猜

---

## 🎁 给后续 AI 的一条建议

**这个项目的核心价值不是代码量，而是"用户能立刻用真实数据做投研"**。

每一次改动都问自己：
- 这功能用户用得上吗？
- 数据真实吗？
- 跑得动吗？
- 测试覆盖了吗？

不是炫技，是解决问题。
