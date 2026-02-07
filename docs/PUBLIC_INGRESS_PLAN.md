# PaperTok 公网发布方案（本地 Mac mini 重算力 + 低配公网服务器做入口）

> 场景：
> - Mac mini 在家/内网运行 PaperTok（MinerU/LLM/VLM/生图等高资源消耗都在本地完成）。
> - 你有一台配置较低、但有公网 IP 的服务器（VPS），希望对外提供访问。
> - 目标是：公网用户访问 **VPS 域名**，VPS 把请求安全、稳定地转发到内网的 Mac mini。
>
> 本文是“工程化计划”，包括：方案选型、里程碑、验收、风险与缓解。

---

## 1) 需求与约束

### 1.1 需求
- 公网用户通过 `https://<your-domain>/` 访问 PaperTok
- 低配 VPS **不承担** MinerU 等重计算，仅做：TLS、反代、限流、缓存、观测
- Mac mini 不需要开放入站公网端口（尽量保持“只出站”）
- 安全要求：
  - 对公网用户限流/防刷
  - 管理面板 `/admin` 必须有强认证（或仅内网可访问）

### 1.2 约束/风险
- Mac mini 在家网络：可能动态公网 IP、NAT、上行带宽有限
- 反代后真实客户端 IP 可能丢失/被篡改（XFF）
- 单点：Mac mini 不在线时服务不可用（除非引入“脱机可服务”的存储同步方案）

---

## 2) 方案总览（可选工具）

下面按“工程复杂度从低到高”列出 3 类方案。

### 方案 A（MVP，最快落地）：SSH Reverse Tunnel + Nginx/Caddy 反代
**核心思路**：Mac mini 主动 SSH 到 VPS，建立反向端口转发；VPS 本地端口再反代到公网。

- Mac mini：维持一条长期连接
  - `ssh -N -R 127.0.0.1:18000:127.0.0.1:8000 user@vps`
- VPS：Nginx/Caddy 监听 443 → proxy_pass 到 `127.0.0.1:18000`

**优点**：
- 不需要额外第三方服务
- 最少组件，1-2 小时可跑通

**缺点**：
- 需要保证 SSH 常驻（建议 autossh + systemd/launchd keepalive）
- 隧道挂了会中断（可通过 watchdog 重连）

适合：先把公网访问跑通，尽快验证产品。

### 方案 B（推荐生产化）：WireGuard VPN + VPS 反代
**核心思路**：用 WireGuard 建一条稳定 VPN，VPS 与 Mac mini 在同一虚拟网段；VPS 反代到 Mac mini 的 VPN IP。

- WireGuard：
  - VPS：wg0（10.66.0.1）
  - Mac：wg0（10.66.0.2）
- VPS：Nginx/Caddy → `http://10.66.0.2:8000`

**优点**：
- 稳定、性能好、易做访问控制
- 不依赖 SSH 保活；网络语义更清晰

**缺点**：
- 初次配置比方案 A 稍复杂

适合：希望长期稳定对外服务。

### 方案 C（最省心/第三方）：Cloudflare Tunnel / Tailscale Funnel
**核心思路**：用现成的“内网穿透”产品让内网服务出现在公网（可选绑定自定义域名）。

**优点**：
- 基本不需要自己维护隧道稳定性
- 通常自带 DDoS/WAF/认证能力

**缺点**：
- 引入第三方依赖（供应商可用性/成本/合规）

适合：你接受第三方，并想极简运维。

---

## 3) 推荐路线（从快到稳）

建议分两阶段：

### Stage 1：先跑通公网访问（方案 A）
交付物：公网域名可访问，HTTPS 正常，基础安全可用。

### Stage 2：再做稳定性与安全加固（迁移到方案 B 或增强 A）
交付物：隧道自愈、限流、监控告警、运维手册。

---

## 4) 关键设计点（PaperTok 侧需要配合的工程项）

### 4.1 访问控制与安全边界
建议策略：
- VPS 侧做 **公网防护**：TLS、BasicAuth/OIDC、限流、WAF（可选）
- Mac mini 侧保持 **强收口**：
  - `PAPERTOK_ALLOWED_CIDRS` 只允许来自 VPN/隧道端点的来源（例如仅允许 `127.0.0.1/32` 或 `10.66.0.1/32`）
  - `PAPERTOK_TRUST_X_FORWARDED_FOR=0`（不要信公网来的 XFF，避免 allowlist 被绕过）
  - `/api/admin/*` 启用 `PAPERTOK_ADMIN_TOKEN`，并建议 VPS 侧再加一层认证或直接不暴露 `/admin`

### 4.2 带宽与缓存
公网用户访问会穿透回家里的上行带宽，建议：
- VPS 反代对静态资源启用缓存：
  - `/assets/*`、`/static/gen*`、`/static/mineru/*` 可做 `proxy_cache` 或 `Cache-Control`
- 或者进一步：把生成图/静态产物同步到 VPS 由 VPS 直接 serve（见“高级方案”）

### 4.3 可用性与降级
如果只做“纯反代”，Mac mini 离线时服务不可用。

可选高级方案（更工程化，后续做）：
- **VPS Serve，Mac 负责生成**（解耦可用性）
  - VPS 部署 PaperTok（只承担读请求 + 静态服务 + DB）
  - Mac mini 作为 worker，通过 VPN 写入 VPS DB/上传产物
  - 公网请求永远打 VPS（即使 Mac 离线也能看历史内容）

---

## 5) 里程碑计划（WBS）

### Phase 0 — 需求确认（0.5 天）
需要你提供/确认：
- 是否有域名？DNS 在哪里管？
- VPS 系统（Ubuntu？）与是否有 root
- 是否接受第三方（Cloudflare/Tailscale）

验收：选定 A/B/C 的路线。

### Phase 1 — MVP 公网可访问（1 天）
**目标**：VPS 域名可访问 PaperTok。

任务（以方案 A 为例）：
1) VPS 安装 Caddy/Nginx（HTTPS）
2) Mac mini 建立 reverse tunnel（建议 autossh）
3) VPS 反代到本地 127.0.0.1:18000
4) 访问控制：
   - VPS 加 BasicAuth（或至少 /admin 单独鉴权）
   - Mac mini allowlist 仅允许 tunnel 来源

验收：
- `https://domain/` 可打开
- `/admin` 受保护（不可匿名访问）
- 压测：至少 10 并发刷新不会把 Mac 打死（可用限流兜底）

### Phase 2 — 稳定性加固（1-3 天）
任务：
- 隧道自愈：
  - autossh/systemd service（VPS）或 launchd（Mac）守护
- 观测：
  - VPS Nginx access log + error log
  - PaperTok `/api/status` 暴露健康信息
- 缓存：
  - VPS 对静态/图片启用 cache
- 安全：
  - rate limit（按 IP/路径）
  - （可选）fail2ban

验收：
- 隧道断开后 30s 内自动恢复
- 日志不会无限增长（轮转策略）

### Phase 3 — 生产化升级（可选，2-7 天）
- 迁移到 WireGuard（方案 B），降低隧道维护成本
- 或升级为“VPS Serve + Mac Worker”解耦方案：
  - VPS 本地 DB/静态目录
  - Mac worker 写入 VPS（通过 API 或直接 DB + 上传）

验收：
- Mac 离线时仍可浏览历史数据
- 生成任务恢复后自动继续补齐

---

## 6) 风险与缓解

1) 家宽上行不足导致慢/不稳定
- 缓解：VPS cache 静态；图片分辨率策略；必要时 VPS serve 静态产物

2) 公网暴露带来攻击面
- 缓解：VPS 入口限流/WAF；/admin 强认证；Mac allowlist 仅允许 VPS

3) 隧道长期不稳定
- 缓解：从 A 迁移到 WireGuard（B）；或用成熟第三方 tunnel（C）

---

## 7) 下一步我需要你回答的 3 个问题（用于落地）

1) 你是否有域名？（例如 `papertok.xxx.com`）还是只用 IP？
2) VPS 系统是什么（Ubuntu/Debian/CentOS）？是否有 root？
3) 你能接受 Cloudflare/Tailscale 这类第三方吗？

> 你回复这 3 个点后，我可以给出“具体到命令级”的实施清单（Nginx/Caddy 配置、autossh/systemd/launchd 文件、PaperTok env 建议值）。
