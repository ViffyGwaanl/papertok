# Public Ingress Plan (Cloudflare Tunnel First)

[English](./CLOUDFLARE_TUNNEL_PLAN.md) | [中文](../CLOUDFLARE_TUNNEL_PLAN.md)

Context:
- You have a domain
- You accept Cloudflare
- You may have a low-spec VPS, but it’s not required

Recommendation: **Do not buy/operate a VPS first**. Use Cloudflare Tunnel to safely expose the Mac mini PaperTok instance. Add a VPS later only if you need stronger availability/caching/backup origin.

---

## Phase A (0.5–1 day): Tunnel → Mac mini
- User → Cloudflare → Tunnel (outbound) → Mac mini → FastAPI
- No inbound ports on the Mac

## Phase B (1–3 days): hardening
- Cloudflare Access for `/admin` and `/api/admin*`
- Rate limiting
- Cache static assets (reduce home uplink)
- Health checks & alerts

## Phase C (optional, 1–2 weeks): add VPS as stable read-only origin
- VPS serves read-only/history/static; Mac mini does generation/writes
- Goal: history still browsable when Mac is offline

---

## Definition of Done (DoD)
- Public site is reachable over HTTPS
- Admin endpoints are not anonymously accessible
- Health check works
- No secrets/data dirs leak

---

## Implementation checklist (high level)
- Cloudflare zone + DNS
- Create Tunnel + ingress to `127.0.0.1:8000`
- Access apps:
  - `/admin*`
  - `/api/admin*`
- PaperTok:
  - `PAPERTOK_ADMIN_TOKEN`
  - choose allowlist strategy

---

## Caching & rate limiting suggestions
- Cache:
  - `/assets/*` (7d)
  - `/static/gen*/*` (7d)
- Rate limit:
  - `/api/papers/random`
  - `/admin*` more strict

---

When you’re ready, use the detailed step-by-step doc:
- `docs/DEPLOY_PAPERTOK_AI_NET_CLOUDFLARE.md`
