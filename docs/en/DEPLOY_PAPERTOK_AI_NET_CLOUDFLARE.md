# Deploy PaperTok on papertok.ai / papertok.net (No VPS, Cloudflare Tunnel)

[English](./DEPLOY_PAPERTOK_AI_NET_CLOUDFLARE.md) | [中文](../DEPLOY_PAPERTOK_AI_NET_CLOUDFLARE.md)

> Goal: expose the PaperTok service running on a Mac mini to the public Internet via Cloudflare Tunnel.
>
> Recommendation: use `papertok.ai` as the **canonical** domain, and redirect `papertok.net` as an **alias** with a full-site **301** to `papertok.ai`.

---

## 0) Pre-flight checklist
- [ ] `papertok.ai` zone is active in Cloudflare (nameservers propagated)
- [ ] (Optional) `papertok.net` zone is active
- [ ] Local health check works: `http://127.0.0.1:8000/healthz` → `{ok:true}`
- [ ] `cloudflared` installed: `cloudflared --version`

---

## 1) Create a Tunnel (run on the Mac mini)

### 1.1 Login
```bash
cloudflared tunnel login
```
Authorize your zone (start with `papertok.ai`).

If you later bind DNS for `papertok.net` and see permission issues, re-run login and authorize that zone.

### 1.2 Create tunnel
```bash
cloudflared tunnel create papertok-mac
```
Record the **Tunnel UUID**.

### 1.3 Route DNS (canonical + optional alias)
Canonical:
```bash
cloudflared tunnel route dns papertok-mac papertok.ai
```

Alias (optional):
```bash
cloudflared tunnel route dns papertok-mac papertok.net
```

---

## 2) Configure ingress
Create `~/.cloudflared/config.yml`:

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

Test run:
```bash
cloudflared tunnel run papertok-mac
```

---

## 3) Run as a daemon
Recommended: run `cloudflared` persistently via launchd (or `brew services`).

### 3.1 Using brew services
```bash
brew services start cloudflared
brew services list | rg cloudflared
```

Note: brew services uses its default config path. If it runs the wrong tunnel/config, switch to a custom launchd plist or move your config to the expected location.

---

## 4) Cloudflare: Force HTTPS (required)

Even if you use Cloudflare Access, you must disable plain HTTP.
HTTP is plaintext and can leak Access cookies and Admin tokens.

In Cloudflare dashboard (papertok.ai zone):
- **SSL/TLS → Edge Certificates → Always Use HTTPS = ON**

Optional (only after you’re sure): enable HSTS.

Verify:
```bash
curl -I http://papertok.ai/
```
Expect `301/308` + `Location: https://papertok.ai/...`

---

## 5) PaperTok-side security (strongly recommended)

### 5.1 Require Admin token for Admin APIs
In `papertok/.env`:
```bash
PAPERTOK_ADMIN_TOKEN=<random>
```
Then `/api/admin/*` requires header `X-Admin-Token`.

### 5.2 IP allowlist strategy
- If the main site is public (admin-only protected), disable allowlist:
```bash
PAPERTOK_ALLOWED_CIDRS=*
```
- If the whole site is private, keep allowlist or make it stricter.

---

## 6) Cloudflare Access (Zero Trust: protect Admin only)

Goal: public site, but **Admin UI** and **Admin API** require login.

### 6.1 Create a reusable policy (allowlisted emails)
Cloudflare Zero Trust:
- Access controls → Policies → Add policy
- Action: ALLOW
- Include: Emails

### 6.2 Alias-domain strategy (choose one)

**Recommended (canonical + 301)**:
- Configure Access only on `papertok.ai` (`/admin*` and `/api/admin*`)
- Redirect `papertok.net/*` → `https://papertok.ai/$1` (301)

Alternative:
- Configure Access apps on both `papertok.ai` and `papertok.net` (higher maintenance)

### 6.3 Create self-hosted app (Admin UI)
- Application URL:
  - Hostname: `papertok.ai`
  - Path: `admin*`
- Bind the allowlist policy

### 6.4 Create self-hosted app (Admin API)
- Hostname: `papertok.ai`
- Path: `api/admin*`

---

## 7) Verification
From an external network (or mobile 5G):
- [ ] `https://papertok.ai/` loads
- [ ] `https://papertok.ai/healthz` returns `{ok:true}`
- [ ] Without login, `https://papertok.ai/admin` redirects to Access login
- [ ] Without login, `https://papertok.ai/api/admin/config` redirects to Access login
- [ ] Even after Access login, backend still requires `X-Admin-Token` (if enabled)
- [ ] `https://papertok.net/` returns **301** to `https://papertok.ai/...`

Recommended regression:
```bash
PAPERTOK_PUBLIC_BASE_URLS="https://papertok.ai,https://papertok.net" \
  ./ops/security_smoke.sh
```

---

## 8) Rollback
- Stop tunnel: `brew services stop cloudflared`
- Remove DNS records in Cloudflare
- Delete tunnel: `cloudflared tunnel delete papertok-mac`
