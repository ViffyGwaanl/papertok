# Public Ingress Plan (Mac mini compute + low-spec VPS as gateway)

[English](./PUBLIC_INGRESS_PLAN.md) | [中文](../PUBLIC_INGRESS_PLAN.md)

Scenario:
- PaperTok runs on a home Mac mini (MinerU/LLM/VLM/image generation).
- You have a low-spec public VPS and want a stable public access point.
- Users hit the **VPS domain**, which securely proxies to the Mac mini.

This is an engineering plan: options, milestones, DoD, risks and mitigations.

---

## 1) Requirements & constraints
- Public access via `https://<your-domain>/`
- VPS should NOT run heavy compute; only TLS, reverse proxy, rate limit, cache, observability
- Mac mini should avoid inbound public ports (prefer outbound tunnels)
- Admin `/admin` must be strongly protected

---

## 2) Options (low → high complexity)

### Option A (fast MVP): SSH reverse tunnel + Nginx/Caddy
- Mac keeps a long-lived reverse tunnel:
  - `ssh -N -R 127.0.0.1:18000:127.0.0.1:8000 user@vps`
- VPS: HTTPS reverse proxy to `127.0.0.1:18000`

Pros: minimal components, quick.
Cons: tunnel keepalive/watchdog needed.

### Option B (recommended production): WireGuard VPN + reverse proxy
- VPS and Mac join the same VPN subnet; VPS proxies to Mac VPN IP.

Pros: stable, clear network semantics.
Cons: initial config more work.

### Option C (managed): Cloudflare Tunnel / Tailscale Funnel
Pros: minimal ops, built-in protections.
Cons: vendor dependency.

---

## 3) Recommended path
- Stage 1: get public access working (Option A)
- Stage 2: harden and stabilize (Option B or improve A)

---

## 4) Key design points (PaperTok side)
- Strong boundary on admin endpoints:
  - Access/BasicAuth on the gateway
  - `PAPERTOK_ADMIN_TOKEN` on backend
- IP allowlist strategy:
  - only allow gateway/VPN sources
  - avoid trusting arbitrary XFF: `PAPERTOK_TRUST_X_FORWARDED_FOR=0`
- Bandwidth/caching:
  - cache `/assets/*` and `/static/gen*/*` on the gateway

Advanced (optional): “VPS serves history, Mac is the worker” to keep history available when Mac is offline.

---

## 5) Milestones
- Phase 0: confirm domain/VPS/3rd party acceptance
- Phase 1: MVP public access
- Phase 2: tunnel self-healing + cache + monitoring + rate limits
- Phase 3: production upgrade (WireGuard or VPS serve + Mac worker)

---

## 6) Risks & mitigations
- Home uplink limitations → cache static content; reduce image sizes; move static to object storage.
- Public attack surface → gateway WAF/rate limits; protect admin; backend token.
- Tunnel instability → autossh/watchdog or migrate to WireGuard/managed tunnel.
