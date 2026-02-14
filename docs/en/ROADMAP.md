# PaperTok Roadmap (Plans & Next Steps)

[English](./ROADMAP.md) | [中文](../ROADMAP.md)

> Principle: prioritize engineering work that improves stability, operability, and portability. Product iteration builds on top of that.

## Current status (done / validated)
- ✅ Cloudflare Tunnel public ingress + Cloudflare Access protects `/admin*` and `/api/admin*`; backend `X-Admin-Token` adds a second gate.
- ✅ Canonical domain: `papertok.net/*` → `papertok.ai/$1` (301, preserve query).
- ✅ Single-origin hosting: backend serves frontend `dist/`; frontend uses `window.location.origin` (no hard-coded `:8000`).
- ✅ `API_BASE` single source of truth: `src/lib/apiBase.ts`.
- ✅ iOS/Android Capacitor internal builds run on real devices; runbooks documented.
- ✅ Android internal distribution: GitHub Releases + `.sha256` verification; also a stable “latest” release (`android-latest`) with fixed asset names.
- ✅ ZH/EN bilingual pipeline (schema + `lang=zh|en|both` API + pipeline + Web UI toggle); EN end-to-end regression complete for latest day.
- ✅ Bilingual backfill converged for last 7 days using strict per-day acceptance (8 metrics).
- ✅ Scheme B (release-based deployment): versioned releases + `current` symlink switches.
- ✅ prod shared de-symlinked: `shared/.env`, `shared/data`, and `shared/venv` are real files/dirs (no dependency on workspace checkout).
- ✅ S0 security hardening:
  - `/api/status` is public summary (no local paths/log paths)
  - `/api/admin/status` is admin-only
  - `/api/papers/{id}` no longer exposes absolute local paths
  - `ops/security_smoke.sh` added as regression

---

## P0 (1–3 days): security & stability finish

1) **Cloudflare: force HTTPS (must-do)**
- Enable *Always Use HTTPS* (or equivalent redirect rule)
- Verify (should hold for every public hostname you expose):
  - `curl -I http://papertok.ai/` → `301/308` → `https://...`

2) **Cloudflare Access: protect every non-public / sensitive entrypoint**
- Already protected: `/admin*` and `/api/admin*`.
- If you expose any additional internal service via Tunnel, it must also be covered by Access (email allowlist).

3) **Frontend diagnosability**
- Clearer error states (network/auth/offline cache hit) + one-click retry
- Timeouts + bounded retries for `/api/papers/random` and `/api/papers/{id}`
- In detail modal: distinguish “missing explanation” vs “request failed”

4) **Jobs safety controls (ops essentials)**
- Admin actions:
  - cancel queued jobs
  - mark running → failed (manual stop)
- Define worker stale-job policy (timeouts, retries, concurrency)

5) **/api/status semantics**
- Current `failed_by_stage` is historical; add a “currently unresolved failures” view
- Reduce noise from historical failures

6) **Health checks: HTTP method compatibility**
- `HEAD /healthz` and `HEAD /api/status` may return 404 while `GET` returns 200.
- Either:
  - A) external health checks use `GET`, or
  - B) add explicit `@app.head` handlers (recommended)

---

## P1 (1–2 weeks): ops engineering

1) **Release retention policy (avoid disk blow-up)**
- Keep last N releases; never delete what `current` points to

2) **Backup/restore**
- Scripted backups for SQLite + key data dirs (pdf/mineru/gen/logs)
- Lightweight option: DB-only backup (derived artifacts can be recomputed)

3) **Config health checks**
- Add a checklist to `/api/status` (public) or `/api/admin/status` (admin):
  - LLM/VLM endpoint reachable?
  - Seedream/GLM keys present?
  - MinerU available?
  - disk space, logs dir writable?

4) **Stronger Admin/Ops**
- One-click retry templates per stage
- Search by `external_id`, filter by stage, aggregate by day

5) **Extra public ingress hardening (optional)**
- Cloudflare WAF/rate limit (especially `/api/papers/*`)
- If write operations are added: CSRF/auth design required

6) **Disk cleanup SOP**
- Keep only prod `shared/venv` + optional dev venv
- Define safe cache cleanup steps for HF/ModelScope (accepting re-download cost)

---

## P2 (long term): portability & scale

1) Portability
- Introduce `PAPERTOK_DATA_DIR` to fully separate code vs data
- Linux/Windows local run (see `PLATFORM_PLAN.md`)

2) Database evolution
- If multi-user or higher write concurrency is needed: SQLite → Postgres

3) Distributed workers
- Multiple workers consuming Jobs across machines

4) Mobile shell
- PWA → Capacitor internal build (see `MOBILE_APP_IMPLEMENTATION.md`)

---

## Engineering management
- Decide long-term GitHub sync strategy:
  1) Make `papertok/` a standalone repo (recommended)
  2) Keep “export snapshot” but with incremental release tooling
