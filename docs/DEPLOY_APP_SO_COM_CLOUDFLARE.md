# app-so.com 上线 PaperTok（无 VPS，Cloudflare Tunnel）

> 目标：不购买 VPS，直接把 Mac mini 上的 PaperTok 通过 Cloudflare Tunnel 暴露到公网。
>
> 默认域名：`papertok.app-so.com`（推荐）

---

## 0) 前置检查

- [ ] `app-so.com` 已在 Cloudflare Dashboard 中激活（Nameserver 已生效）
- [ ] 本机 PaperTok 可访问：`http://127.0.0.1:8000/healthz` 返回 `{ok:true}`
- [ ] 本机已安装 cloudflared：`cloudflared --version`

---

## 1) 创建 Tunnel（Mac mini 上执行）

### 1.1 登录授权
```bash
cloudflared tunnel login
```
在浏览器里选择并授权 Zone：`app-so.com`。

授权成功后，会在 `~/.cloudflared/` 下生成证书文件。

### 1.2 创建 tunnel
```bash
cloudflared tunnel create papertok-mac
```
记录输出的 **Tunnel UUID**。

### 1.3 绑定 DNS
```bash
cloudflared tunnel route dns papertok-mac papertok.app-so.com
```

---

## 2) 配置 ingress（Mac mini）

创建 `~/.cloudflared/config.yml`：
```yaml
tunnel: <TUNNEL-UUID>
credentials-file: /Users/<YOU>/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: papertok.app-so.com
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

因为 Tunnel 会把你的服务暴露到公网，建议至少做两层保护：

### 4.1 Admin API 强制 Token
在 `papertok/.env` 设置：
```bash
PAPERTOK_ADMIN_TOKEN=<random>
```

这样 `/api/admin/*` 与 `/api/admin/jobs/*` 必须带 `X-Admin-Token`。

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

### 5.2 创建自托管应用（Admin UI）
- **Access controls → Applications → Add an application → Self-hosted**
- Application URL：
  - Hostname：`papertok.app-so.com`
  - Path：`admin*`
- 创建后进入该应用的 **Edit → 策略**
  - 选择现有策略（Select existing policy）
  - 勾选上一步创建的“允许邮箱”策略
  - 保存应用

> 备注：Path 通常不需要前导 `/`；用 `admin*` 可覆盖 `/admin` 和 `/admin/xxx`。

### 5.3 创建自托管应用（Admin API）
同样创建一个 Self-hosted 应用：
- Hostname：`papertok.app-so.com`
- Path：`api/admin*`
- 在 **Edit → 策略** 里绑定同一条“允许邮箱”策略并保存。

> 为什么拆两个应用：路径更清晰、策略可独立调整；且 `/api/admin*` 一定要保护，否则别人可以直接打 API。

### 5.4 healthz 是否需要 bypass？
- 推荐：`/healthz` 不走 Access（保持公开），方便你做健康检查和排障。
- 因为我们是“只保护 /admin* 与 /api/admin*”，所以 `/healthz` 默认不会被 Access 影响。

---

## 6) 验收

外网执行（或手机 5G）：
- [ ] `https://papertok.app-so.com/` 正常打开
- [ ] `https://papertok.app-so.com/healthz` 返回 `{ok:true}`
- [ ] 未登录时：访问 `/admin` 会被 **302** 到 Cloudflare Access 登录页
- [ ] 未登录时：访问 `/api/admin/config` 会被 **302** 到 Cloudflare Access 登录页
- [ ] 登录后：仅允许的邮箱能通过；其他邮箱被拒绝
- [ ] 即使通过 Access，后端仍要求 `X-Admin-Token`（如果你设置了 `PAPERTOK_ADMIN_TOKEN`）

---

## 7) 回滚

- 停 tunnel：`brew services stop cloudflared`
- 删除 DNS route：在 Cloudflare DNS 中删除 `papertok` 记录
- 删除 tunnel：`cloudflared tunnel delete papertok-mac`
