# PaperTok Security（安全模型 / 防护分层）

> 目标：PaperTok 默认“本地单机跑”；当你通过 Cloudflare Tunnel 上公网时，也能保持足够安全的边界。

## 1) 威胁模型（简版）

- **默认场景（LAN-only）**：风险主要来自同一局域网内的其他设备误访问/扫描。
- **公网场景（Cloudflare Tunnel）**：任何人都能访问到你的域名；风险包括：
  - 直接调用 Admin API
  - 暴力尝试/扫描
  - 前端缓存/错误配置导致误暴露
  - 未来若加入写操作（收藏/评论/账号）会引入更复杂的鉴权与 CSRF 风险

## 2) 分层防护（Defense in Depth）

### 2.0 公网信息泄露基线（必须满足）
- 公网的 `GET /api/*` 响应 **不得**包含：
  - 本机绝对路径（例如 `/Users/...`）
  - 运维日志路径（例如 `log_path`）
  - 管理队列/worker 细节（jobs 列表等）

建议把这条写成回归测试（见 `ops/security_smoke.sh`）。

备注：PaperTok 已将状态接口分为 public/admin 两个层级：
- `GET /api/status` / `GET /api/public/status`：公共摘要（可公开）
- `GET /api/admin/status`：管理版详细状态（必须在 Access + `X-Admin-Token` 保护之下）

PaperTok 推荐把防护拆成 4 层（从外到内）：

### L1：Cloudflare（边缘层）
- **Cloudflare Tunnel**：由本机主动建立到 Cloudflare 的出站连接；无需开端口映射。
- **强制 HTTPS（必须）**：开启 Cloudflare 的 *Always Use HTTPS*（或等价的 Redirect Rule），确保 `http://` 永远重定向到 `https://`。
  - 原因：HTTP 明文可被窃听/篡改；对 Access cookie / Admin Token 尤其危险。
  - 验收（对每个对外暴露的 hostname 都应成立）：
    ```bash
    curl -I http://papertok.ai/
    ```
    应返回 `301/308` 且 `Location: https://...`。
- 可选：WAF / Rate limiting（当访问量上来或被扫时再加）。

### L2：Cloudflare Access（身份层）
- 建议用 Access 保护管理面（推荐主域 `papertok.ai`）：
  - `papertok.ai/admin*`
  - `papertok.ai/api/admin*`

  对于别名域 `papertok.net`，推荐做 **301 永久重定向**到 `papertok.ai`，从而无需再维护第二套 Access 配置。

- **额外建议（强烈）**：对任何“非公开内部服务入口”也开启 Access。
  - 例如：本地网关/工具服务等，只要对公网开放，就必须 Access（邮箱 allowlist）+ 速率限制。

### L3：后端管理口令（应用层）
- `PAPERTOK_ADMIN_TOKEN`：启用后，所有 `/api/admin/*` 需要 `X-Admin-Token`。
- 管理运维接口（如 `/api/admin/status`、`/api/admin/jobs/*`）应始终保持在该保护之下。
- 作用：即使 Access 配错/被绕过，也能挡住直接 API 调用。

### L4：IP allowlist / Basic Auth（网络/补充层）
- `PAPERTOK_ALLOWED_CIDRS`：默认只允许私网与 localhost。
- `PAPERTOK_BASIC_AUTH=1`：可对整个站点加一层 Basic Auth（适合临时演示/小范围共享）。

> 公网推荐组合：**Access + Admin Token**，主站可公开；若还要更严，叠加 IP allowlist。

## 3) 公网推荐配置（示例）

### 3.1 主站公开、只保护 Admin（推荐）
`.env`：
- `PAPERTOK_ALLOWED_CIDRS=*`
- `PAPERTOK_ADMIN_TOKEN=...`（随机长串）

Cloudflare Access：
- 两个 Self-hosted 应用：`admin*` + `api/admin*`
- 绑定“仅允许指定邮箱”的可重用策略

域名：
- 推荐将 `papertok.net/*` **301 永久重定向**到 `https://papertok.ai/$1`，避免出现“某个别名域忘了做 Access”的安全配置漂移。

### 3.2 继续使用 IP allowlist（更严格）
如果你想限制为“只有某些公网 IP 能访问”，并且前面有 Cloudflare 代理：
- `PAPERTOK_TRUST_X_FORWARDED_FOR=1`
- `PAPERTOK_ALLOWED_CIDRS=<your_ip_cidrs>`

## 4) 密钥与敏感信息

- **所有密钥只放 `papertok/.env`**，不要提交到 git。
- `.env.example` 只做模板，不要放真实 token/key。
- 日志中避免输出完整 key/token（必要时只输出前后几位）。

## 5) 未来功能的安全注意事项（前瞻）

- 一旦加入“写入型”功能（收藏同步、评论、用户系统），需要补齐：
  - 认证（AuthN）与授权（AuthZ）
  - CSRF 防护（如果走 cookie/session）
  - 速率限制与滥用防护
  - 审计日志（谁做了什么）
