# Issue 02: data_fetcher.log 无限膨胀（984MB，无轮转）

Status: ready-for-agent

## 描述

`backend/data_fetcher.log` 已膨胀至 ~984MB（2026-08-25 实测 984917331 字节），无任何轮转机制：

- 根因：监控流每 30s 刷新，HK 数据源在 Clash TUN 干扰下反复 `ConnectionResetError`，每条失败写完整 traceback
- 已确认根因是 Clash 虚拟网卡（TUN/fake-IP）干扰，https 自动降级已上线（见 `.scratch/eastmoney-proxy/` 结论），但失败 traceback 仍在持续写盘
- 磁盘占用接近 1GB，长期运行会持续膨胀；`du` 实测 945M

## 建议

- 给 `data_fetcher.py` 的 logger 加 RotatingFileHandler（如 10MB × 10 个，或 TimedRotatingFileHandler 按天轮转）
- 或：HK 源失败 traceback 降级为单行 summary（连接重置属预期内降级路径，不必每次写全 traceback）
- 顺手把现有 984MB 日志截断/清理（不可逆操作，需用户确认；或直接建议用户删）

## 备注

- 发现时间：2026-08-25，/chart 白屏修复专项（agent-teams 团队 t1 诊断附带发现）
- 尾部内容实测为 HK 源 `ConnectionResetError` traceback，与 Clash TUN 根因吻合
