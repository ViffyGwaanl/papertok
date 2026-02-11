# PaperTok Security (Threat Model & Defense-in-Depth)

[English](./SECURITY.md) | [中文](../SECURITY.md)

> Goal: PaperTok is local-first. If you expose it to the public Internet via Cloudflare Tunnel, it should still maintain a safe security boundary.

## 1) Threat model (short)

- **LAN-only default**: risks mainly come from other devices on the same network scanning/mis-clicking.
- **Public (Cloudflare Tunnel)**: anyone can reach your domain; risks include:
  - Direct calls to admin APIs
  - Scanning / brute force
  - Misconfiguration or caching bugs leaking sensitive data
  - Future write operations (likes/comments/accounts) introducing auth + CSRF risks

## 2) Defense in Depth

### 2.0 Public data-leak baseline (must hold)
Public `GET /api/*` responses must NOT include:
- Local absolute paths (e.g. `/Users/...`)
- Ops log paths (e.g. `log_path`)
- Admin queue/worker details (jobs list, etc.)

Make this a regression test: `ops/security_smoke.sh`.

PaperTok splits status endpoints:
- `GET /api/status` / `GET /api/public/status`: public summary
- `GET /api/admin/status`: admin-only detailed status (must be behind Access + `X-Admin-Token`)

### L1: Cloudflare (edge)
- **Cloudflare Tunnel**: outbound connection; no port forwarding.
- **Force HTTPS (required)**: enable *Always Use HTTPS* (or equivalent redirect rule) so `http://` always redirects to `https://`.
  - Reason: HTTP is plaintext and can be sniffed/modified; dangerous for Access cookies and Admin tokens.
  - Verify:
    ```bash
    curl -I http://papertok.ai/
    ```
    Expect `301/308` with `Location: https://papertok.ai/...`.
- Optional: WAF / rate limiting once you see scans or real traffic.

### L2: Cloudflare Access (identity)
Protect admin surfaces (recommended on canonical `papertok.ai`):
- `papertok.ai/admin*`
- `papertok.ai/api/admin*`

For the alias domain `papertok.net`, prefer a full-site **301** to `papertok.ai` to avoid maintaining a second Access config.

Policy: allowlist your email(s), using One-time PIN or an IdP.

### L3: Backend admin token (application)
- Set `PAPERTOK_ADMIN_TOKEN` and require header `X-Admin-Token` for `/api/admin/*`.
- Even if Access is misconfigured, this blocks direct admin API calls.

### L4: IP allowlist / Basic Auth (network / extra)
- `PAPERTOK_ALLOWED_CIDRS`: allow private LAN + localhost by default.
- `PAPERTOK_BASIC_AUTH=1`: optional site-wide Basic Auth for temporary demos.

Recommended public combo: **Access + Admin Token**. Add IP allowlist if you want stricter constraints.

## 3) Recommended public config (examples)

### 3.1 Public site, protect admin only (recommended)
`.env`:
- `PAPERTOK_ALLOWED_CIDRS=*`
- `PAPERTOK_ADMIN_TOKEN=...` (random long string)

Cloudflare Access:
- Two self-hosted apps: `admin*` and `api/admin*`

Domains:
- Redirect `papertok.net/*` → `https://papertok.ai/$1` (301)

### 3.2 Keep IP allowlist (stricter)
If you want to only allow certain public IPs and you are behind Cloudflare:
- `PAPERTOK_TRUST_X_FORWARDED_FOR=1`
- `PAPERTOK_ALLOWED_CIDRS=<your_ip_cidrs>`

## 4) Secrets & sensitive data
- Put all secrets only in `papertok/.env` (gitignored)
- `.env.example` is a template only
- Avoid logging full keys/tokens

## 5) Forward-looking notes
Once you add write operations (sync likes, comments, user system), you must design:
- AuthN/AuthZ
- CSRF protection (if cookies/sessions)
- Rate limits / abuse prevention
- Audit logs
