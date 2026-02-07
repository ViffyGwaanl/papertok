# PaperTok 公网发布（Cloudflare Tunnel 优先）计划

> 你当前条件：
> - 有域名
> - 接受 Cloudflare
> - 暂时未购买 GCP VPS（且 VPS 配置较低）
>
> 推荐：**先不买 VPS**，直接用 Cloudflare Tunnel 把家里 Mac mini 的 PaperTok 安全暴露到公网；等验证流量与稳定性后，再决定是否引入 VPS 做“历史可用/静态缓存/备份 origin”。

---

## 0) 方案结论（推荐路径）

### Phase A（最快上线，0.5~1 天）：Cloudflare Tunnel → Mac mini
- 公网访问路径：用户 → Cloudflare（TLS/WAF/限流/可选 Access）→ Tunnel（出站）→ Mac mini → FastAPI
- Mac mini 不需要任何入站公网端口
- VPS 不参与数据面（只在你未来需要时作为增强）

### Phase B（增强稳定与安全，1~3 天）：Access + WAF + Cache Rules + 监控
- `/admin` 强身份认证（Cloudflare Access）
- API 限流、防刷
- 静态资源缓存（减轻家宽上行）
- 健康检查与告警

### Phase C（可选，后续 1~2 周）：引入 VPS 作为“稳定 origin/历史可用”
- 架构升级：VPS Serve（只读与静态）+ Mac Worker（负责生成/写入）
- 目标：Mac 离线时仍可浏览历史内容

---

## 1) 工程化需求与验收标准（DoD）

### 1.1 MVP 上线（DoD-A）
- [ ] `https://papertok.<domain>/` 可访问
- [ ] `https://papertok.<domain>/admin` 不允许匿名访问（至少需要 Access 或强口令）
- [ ] `https://papertok.<domain>/api/admin/*` 不允许匿名访问（必须被 Access 保护；后端可再叠加 admin token）
- [ ] `GET /healthz` 可用，外部监控可探测
- [ ] 不泄露 secrets：`.env`、`data/`、数据库均不出内网

### 1.2 稳定性与安全（DoD-B）
- [ ] 限流：对 `/api/*`、`/admin*` 有 rate limit
- [ ] WAF：基础 bot/爬虫防护启用
- [ ] 缓存：`/assets/*`（前端）与 `/static/gen*/*`（生成图）启用缓存策略
- [ ] 监控：Tunnel 断线/服务不可用可告警

### 1.3 生产化升级（DoD-C，可选）
- [ ] Mac 离线时，VPS 仍可提供历史浏览（只读）
- [ ] 数据同步可追溯（jobs/events），并可恢复

---

## 2) 实施清单（命令级）

> 假设：你的域名 DNS 已托管到 Cloudflare（或至少让 Cloudflare 管理该子域）。

### 2.1 Cloudflare 侧准备
1) Cloudflare Dashboard：添加/接管域名
2) 规划子域名：`papertok.<domain>`
3) （推荐）创建 Access 应用（拆两条路径更清晰）：
   - Admin UI：`https://papertok.<domain>/admin*`
   - Admin API：`https://papertok.<domain>/api/admin*`
   - 身份源：Google / GitHub / 邮箱一次性码
   - Policy：只允许你的账号/邮箱域

### 2.2 Mac mini 安装 cloudflared
```bash
brew install cloudflared
cloudflared --version

# 登录授权（会打开浏览器）
cloudflared tunnel login
```

### 2.3 创建 Tunnel + 绑定域名
```bash
# 创建 tunnel
cloudflared tunnel create papertok-mac

# 绑定 DNS（将 papertok.<domain> 指向该 tunnel）
cloudflared tunnel route dns papertok-mac papertok.<domain>
```

### 2.4 配置转发到本机 PaperTok
创建 `~/.cloudflared/config.yml`：
```yaml
tunnel: <TUNNEL-UUID>
credentials-file: /Users/<you>/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: papertok.<domain>
    service: http://127.0.0.1:8000
  - service: http_status:404
```

启动测试：
```bash
cloudflared tunnel run papertok-mac
```

### 2.5 将 cloudflared 作为常驻服务
```bash
# macOS launchd service
sudo cloudflared service install

# 启动/查看状态
sudo launchctl kickstart -k system/com.cloudflare.cloudflared
sudo launchctl list | rg cloudflared || true
```

> 注：如果你更希望“按用户级 launchd”（非 system），我们可以换一种安装方式；system 级通常更稳定。

---

## 3) PaperTok 配置建议（公网化安全配置）

### 3.1 `/admin` 与 `/api/admin/*` 双重保护
- Cloudflare Access（路径级）作为第一道门
- PaperTok 内部再启用 admin token：
  - `.env`：`PAPERTOK_ADMIN_TOKEN=...`
  - 前端 Admin 页面会提示填 token（本地存储）

### 3.2 IP allowlist 的推荐设置
你现在 PaperTok 默认允许私网段 + localhost。

若你希望“公网只走 Tunnel、局域网手机也能直接访问”：
- 保持默认（允许 192.168/10/172 + 127.0.0.1）即可。

若你希望“彻底禁止局域网直连（更安全）”：
- 设置：`PAPERTOK_ALLOWED_CIDRS=127.0.0.1/32,::1/128`
- 这样只有本机（包括 cloudflared 本机转发）能访问；手机必须走 `https://papertok.<domain>/`

### 3.3 不信任 XFF（防绕过）
- 保持默认：`PAPERTOK_TRUST_X_FORWARDED_FOR=0`
- 客户端无法通过伪造 XFF 绕过 allowlist

---

## 4) Cloudflare 缓存/限流建议（减轻家宽上行）

### 4.1 Cache Rules（建议）
- `papertok.<domain>/assets/*`：Cache Everything，TTL 7d
- `papertok.<domain>/static/gen/*`：TTL 7d
- `papertok.<domain>/static/gen_glm/*`：TTL 7d
- `papertok.<domain>/static/mineru/*`：谨慎缓存（可能大且多），可先不开或 TTL 1d

### 4.2 Rate Limiting（建议）
- 对 `/api/papers/random`：按 IP 每分钟限制（例如 60-120 次）
- 对 `/api/papers/*`：适中限制
- 对 `/admin*`：更严格

---

## 5) 引入 GCP VPS 的“合理理由”（什么时候值得买）

你在接受 Cloudflare 后，VPS **不是必需品**。建议等以下任一情况出现再买：

1) 你希望 **Mac 离线时仍能访问历史内容**
- 需要 VPS 承担“只读 origin + 静态服务 + DB 存储”

2) 你希望 **把大静态资源迁走**（例如大量生成图 / MinerU 抽图）
- VPS 或对象存储（R2/S3）更合适

3) 你希望更强的监控/告警/集中日志

---

## 6) 风险与缓解

1) PWA/SW 缓存导致前端更新不生效
- 缓解：文档化“无痕打开/清站点数据”；必要时对 build 版本做显式版本号提示

2) 家宽上行不足
- 缓解：Cloudflare 缓存静态；控制图像尺寸；必要时将静态迁移到 R2

3) 安全风险（爬虫/爆破）
- 缓解：Access + Rate Limit + WAF；Admin token 双保险

---

## 7) 你接下来需要给我的信息（我才能把命令替换成可直接复制）

1) 你的域名是什么？计划用哪个子域（例如 `papertok.example.com`）
2) 你域名 DNS 是否已经在 Cloudflare 托管？（是/否）
3) `/admin` 你希望用哪种 Access：
   - A) 仅允许你的 Google 账号
   - B) 仅允许特定邮箱列表
   - C) 临时用一次性 PIN 邮箱登录

> 你回复这三项后，我可以给你一份“完全可复制粘贴”的落地步骤（包含 config.yml、Access policy、Cache/Rate Rule 建议值）。
