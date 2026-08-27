# Issue 01: 修复监控页新增股票

Status: done

## What to build

让 `POST /api/stocks/` 接受页面提示的 A 股 / 港股后缀写法，规范化后按实际代码入库；支持可选显示名，并确保规范化后不重复添加。

## Acceptance criteria

- [x] `600519.SS` 添加后返回 `ticker=600519`、`market=CN`
- [x] `700.HK` 添加后返回 `ticker=00700`、`market=HK`
- [x] 手填名称会出现在新增股票响应和数据库中
- [x] `600519.SS` 与 `600519` 不会重复添加
- [x] 测试使用临时库且不访问外部行情

## Blocked by

None

## Comments

- 2026-08-27：为避免与首页优化会话冲突，改动范围限定为后端模型、路由与监控服务；不触碰 `Dashboard.jsx`。
- 2026-08-28：完成。先写入 6 个临时 SQLite API 回归测试并确认旧实现失败，再实现代码格式归一、手填名称和规范化判重。验证：`backend/test_stock_management.py` 6/6、根目录后端测试 25/25、量化测试 232/232；数据抓取冒烟、前端 lint/build 通过。
