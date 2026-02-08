# papertok.ai / papertok.net 上线 PaperTok（无 VPS，Cloudflare Tunnel）

> 目标：不购买 VPS，直接把 Mac mini 上的 PaperTok 通过 Cloudflare Tunnel 暴露到公网。
>
> 推荐：以 `papertok.ai` 作为**主域（canonical）**，`papertok.net` 作为**别名（alias）**并对全站做 **301 永久重定向**到 `papertok.ai`。

---

## 0) 前置检查

- [ ] `papertok.ai` 已在 Cloudflare Dashboard 中激活（Nameserver 已生效）
- [ ] （可选）`papertok.net` 也已在 Cloudflare 中激活（Nameserver 已生效）
- [ ] 本机 PaperTok 可访问：`http://127.0.0.1:8000/healthz` 返回 `{ok:true}`
- [ ] 本机已安装 cloudflared：`cloudflared --version`

---

## 1) 创建 Tunnel（Mac mini 上执行）

### 1.1 登录授权
```bash
cloudflared tunnel login
```
在浏览器里选择并授权你的 Zone（建议先选 `papertok.ai`）。

> 如果你后续为 `papertok.net` 绑定 DNS 时提示没有权限，重新执行一次 `cloudflared tunnel login` 并选择 `papertok.net` 即可。

授权成功后，会在 `~/.cloudflared/` 下生成证书文件。

### 1.2 创建 tunnel
```bash
cloudflared tunnel create papertok-mac
```
记录输出的 **Tunnel UUID**。

### 1.3 绑定 DNS（主域 + 可选别名）
主域：
```bash
cloudflared tunnel route dns papertok-mac papertok.ai
```

别名（可选）：
```bash
cloudflared tunnel route dns papertok-mac papertok.net
```

---

## 2) 配置 ingress（Mac mini）

创建 `~/.cloudflared/config.yml`：
```yaml
tunnel: <TUNNEL-UUID>
credentials-file: /Users/<YOU>/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: papertok.ai
    service: http://127.0.0.1:8000
  - hostname: papertok.net
    service: http://127.0.0.1:8000
  - service: http_status:404
```

启动测试：
```bash
cloudflared tunnel run papertok-mac
```

---

## 3) 常驻运行（建议）

推荐把 cloudflared 做成 launchd 常驻（或用 brew services）。

### 3.1 brew services（最省事）
```bash
brew services start cloudflared
brew services list | rg cloudflared
```

> 注意：brew service 默认读它的配置位置。若遇到“没按你的 tunnel 跑”，建议改用自定义 launchd plist，或把 config 放到 brew 的默认配置目录。

---

## 4) PaperTok 侧安全配置（强烈建议）

因为 Tunnel 会把你的服务暴露到公网，建议至少做两层保护。

### 4.1 Admin API 强制 Token
在 `papertok/.env` 设置：
```bash
PAPERTOK_ADMIN_TOKEN=<random>
```

这样 `/api/admin/*` 必须带 `X-Admin-Token`。

### 4.2 IP Allowlist 的策略
- 如果你希望主站公开（只限制 admin），建议关闭 allowlist：
```bash
PAPERTOK_ALLOWED_CIDRS=*
```

- 如果你希望整个站点只给自己用，则保持默认 allowlist 或改成更严格的白名单。

---

## 5) Cloudflare Access（Zero Trust：只限制 Admin）

目标：主站公开访问，但 **Admin UI** 和 **Admin API** 仅允许指定邮箱账号登录。

### 5.1 创建可重用策略（仅允许指定邮箱）
在 Cloudflare Zero Trust：
- **Access controls → Policies → Add policy**
- Action：`ALLOW`
- Include：`Emails` → 填你的邮箱（如 `qq983929606@gmail.com`）
- 保存

### 5.2 选择“别名域”的策略（两种二选一）

**推荐（canonical + 301）**：
- 只把 Cloudflare Access 配在 `papertok.ai`（`/admin*` + `/api/admin*`）
- 把 `papertok.net/*` **301 永久重定向**到 `https://papertok.ai/$1`（保留 path + query）

好处：
- Access 只需维护一套
- App/文档/分享链接统一用主域，减少不必要的重定向

> 注意：301 有缓存效应（浏览器/中间层可能会记住），不要频繁来回切。

#### 5.2.1 配置 `papertok.net → papertok.ai` 301 重定向（Cloudflare Redirect Rules）
在 Cloudflare Dashboard 的 `papertok.net` Zone：
- **Rules → Redirect Rules → Create rule**
- Match：**All incoming requests**
- Type：Dynamic
- Target URL (Expression)：
  - `concat("https://papertok.ai", http.request.uri.path)`
- Status code：`301`
- Preserve query string：✅
- Deploy

验收（推荐用 curl，避免浏览器缓存干扰）：
```bash
curl -I https://papertok.net/
curl -I https://papertok.net/api/status
curl -I https://papertok.net/admin
```
期望：`Location` 指向 `https://papertok.ai/...`。

**备选（两个域都可直连）**：在 `papertok.ai` 与 `papertok.net` 各自创建一套 Access Applications。
- 好处：两个域都能直接访问，不依赖跳转
- 代价：维护面更大（更容易出现“某个域忘了保护”的配置漂移）

### 5.3 创建自托管应用（Admin UI）
- **Access controls → Applications → Add an application → Self-hosted**
- Application URL：
  - Hostname：`papertok.ai`
  - Path：`admin*`
- 创建后进入该应用的 **Edit → 策略**：
  - 选择现有策略（Select existing policy）
  - 勾选上一步创建的“允许邮箱”策略
  - 保存应用

> 如果你选择“两个域都可直连”的备选策略（不做 301），则照抄创建一份 Hostname 为 `papertok.net` 的应用。

### 5.4 创建自托管应用（Admin API）
同样创建一个 Self-hosted 应用：
- Hostname：`papertok.ai`
- Path：`api/admin*`
- 在 **Edit → 策略** 里绑定同一条“允许邮箱”策略并保存。

> 如果你选择“两个域都可直连”的备选策略（不做 301），则照抄创建一份 Hostname 为 `papertok.net` 的应用。

---

## 6) 验收

外网执行（或手机 5G）：

主域：
- [ ] `https://papertok.ai/` 正常打开
- [ ] `https://papertok.ai/healthz` 返回 `{ok:true}`
- [ ] 未登录时：访问 `https://papertok.ai/admin` 会被 **302** 到 Cloudflare Access 登录页
- [ ] 未登录时：访问 `https://papertok.ai/api/admin/config` 会被 **302** 到 Cloudflare Access 登录页
- [ ] 即使通过 Access，后端仍要求 `X-Admin-Token`（若设置了 `PAPERTOK_ADMIN_TOKEN`）

别名（推荐开启）：
- [ ] `https://papertok.net/` 返回 **301** 并跳转到 `https://papertok.ai/`（保留 path + query）

回归测试（推荐）：
```bash
PAPERTOK_PUBLIC_BASE_URLS="https://papertok.ai,https://papertok.net" \
  ./ops/security_smoke.sh
```

---

## 7) 回滚

- 停 tunnel：`brew services stop cloudflared`
- 删除 DNS route：在 Cloudflare DNS 中删除 `papertok.ai` / `papertok.net` 记录
- 删除 tunnel：`cloudflared tunnel delete papertok-mac`
