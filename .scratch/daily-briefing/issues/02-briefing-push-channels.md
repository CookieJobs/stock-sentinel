# Issue 02: 简报推送渠道（飞书/Lark、邮件）

Status: ready-for-human

## 描述

每日简报目前只站内展示（`/api/briefings/`）+ 手动生成。希望支持定时推送：

- 飞书/Lark 机器人（项目已有 lark 生态可用）
- 邮件

## 建议

- 复用 `alerter.py` 的 `ALERT_WEBHOOK_URL` 模式，新增 `BRIEFING_WEBHOOK_URL` 配置
- 在 `BriefingGenerator.generate()` 成功后追加推送钩子
- 注意：接入推送渠道涉及外部服务与凭据，按 `AGENTS.md`“必须升级给用户的边界”需人工确认后再实现
