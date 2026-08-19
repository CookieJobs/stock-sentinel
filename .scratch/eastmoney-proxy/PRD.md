# PRD: 东财 API 连通性根因 — Clash fake-IP 路由规则拦截

Status: ready-for-human
Owner: agent
Version: 1.0
Date: 2026-08-18

## 问题

`push2.eastmoney.com` / `push2his.eastmoney.com` 行情接口时通时不通；代码里东财 URL 被降级为 http
（见 `backend/data_fetcher.py` 注释 + CHANGELOG 2026-08-15），被标为安全债。

## 诊断结论（已实证）

1. 本机运行 **Clash Party（mihomo）**，TUN/fake-IP 增强模式劫持了全部 DNS 与流量。
2. `push2.eastmoney.com` 解析到 `198.18.0.63`、`push2his.eastmoney.com` 解析到 `198.18.0.72`
   —— 属 198.18.0.0/16 fake-IP 段（RFC 2544 保留段），**非东财真实 IP**。
3. 对照：`finnhub.io` 也解析到 fake-IP `198.18.0.70`，但因其代理规则正常而可达（HTTP 401 需 key）。
4. 现象：东财 https 直连 `Remote end closed connection without response`（TLS 后被重置），
   http 直连同样被重置或 502；系统代理（Clash HTTP 端口）对 https 报 ProxyError、对 http 报 502。

**结论**：根因不在 http/https，而在 Clash 对东财两个域名的 fake-IP 路由规则是坏的（大概率命中了一个
失效节点或未正确直连）。`data_fetcher.py` 的 http 降级是治标 workaround，未真正解决。

## 修复建议（需人工，改代理配置非代码）

任选其一：

1. **推荐**：Clash Party 里给东财加直连规则，置于兜底代理规则之前：
   ```
   DOMAIN-SUFFIX,push2.eastmoney.com,DIRECT
   DOMAIN-SUFFIX,push2his.eastmoney.com,DIRECT
   ```
   （或直接 `DOMAIN-SUFFIX,eastmoney.com,DIRECT` 覆盖整个东财域名。）
2. 若不需要代理接管国内流量：关闭 Clash 的 TUN/增强模式，或把东财域名加入直连绕过列表。
3. 验证：`nslookup push2.eastmoney.com` 应返回真实公网 IP（非 198.18.x.x），且
   `curl https://push2.eastmoney.com/...` 返回 200。

## 后续

- 代理规则修好后，可将 `backend/data_fetcher.py` 的东财 URL 改回 https（消掉安全债）。
- 本 issue 完成前，代码保持 http workaround 不动。

## 测试更新（2026-08-19，用户改 Clash 规则后）

1. DNS 已恢复真实 IP（`push2` → 101.226.x、`push2his` → 14.103.x/117.184.x，不再 198.18.x）——**DIRECT 规则生效**。
2. 但 `push2`/`push2his` 的 http 与 https 请求仍被服务端在 0.15–2s 内 `RemoteDisconnected` 秒断，不给响应；
   `data_fetcher` 仍回退 demo。
3. 对照：腾讯 `qt.gtimg.cn`、新浪 `hq.sinajs.cn`、东财 `datacenter-web.eastmoney.com` 均 200 正常。
   → **问题精确锁定在 push2/push2his 两个实时行情接口本身**（疑似 TLS 指纹 / 缺失会话 token / IP 风控），
   并非网络或 Clash。Clash 规则是必要修复，但非充分。
4. 下一步方向：改用东财备用行情域名（如 `push2delay.eastmoney.com`）或腾讯/新浪行情作为 CN/HK 实时源，
   或研究 push2 所需的确切请求参数/`ut` token（当前硬编码公共 token 已无效）。

