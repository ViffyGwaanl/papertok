# PaperTok Roadmap (Plans & Next Steps)

[English](./ROADMAP.md) | [中文](../ROADMAP.md)

> Principle: prioritize engineering work that improves stability, operability, and portability. Product iteration builds on top of that.

## Current status
- ✅ Cloudflare Tunnel public ingress + Cloudflare Access protects `/admin*` and `/api/admin*`; backend `X-Admin-Token` adds a second gate.
- ✅ Canonical domain: `papertok.net/*` → `papertok.ai/$1` (301, preserve query).
- ✅ Same-origin on mobile/public: frontend uses `window.location.origin` (no hard-coded `:8000`).
- ✅ `API_BASE` single source of truth: `src/lib/apiBase.ts`.
- ✅ iOS/Android Capacitor internal build runs on real devices.
- ✅ ZH/EN bilingual pipeline (schema + `lang=zh|en|both` API + pipeline + Web UI toggle) and EN end-to-end regression for latest day.
- ✅ S0 security hardening:
  - `/api/status` is public summary (no local paths/log paths)
  - `/api/admin/status` is admin-only
  - `/api/papers/{id}` no longer exposes absolute local paths
  - `ops/security_smoke.sh` added as regression

---

## P0 (1–3 days): stability & UX

1) **Cloudflare: force HTTPS (must-do)**
- Enable *Always Use HTTPS* (or equivalent redirect rule)
- Verify: `curl -I http://papertok.ai/` → `301/308` → `https://...`

2) **Bilingual production backfill (make EN truly usable)**
- Latest day EN is complete; decide backfill scope:
  - A) last 7/30 days
  - B) full history (higher cost; must throttle/queue)
- Standard operating procedure: enqueue by `day`/`lang` batches (avoid “run all” in one shot)

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
- Current `failed_by_stage` is historical; add “currently unresolved failures” view
- Reduce noise from historical failures

6) **Internal distribution (keep apps in sync with web)**
- App shells do not auto-update web assets; every frontend change requires rebuilding/releasing a new app build.
- iOS: runbook for Archive → TestFlight or Development `.ipa`
- Android: keystore config + publish a new signed release APK with ZH/EN toggle (`versionCode` bump)

---

## P1 (1–2 weeks): ops engineering

0) **Finish Scheme B isolation: prod `shared/venv`**
- Rebuild `~/papertok-deploy/shared/venv` using Python 3.13
- Recommend `PIP_NO_CACHE_DIR=1` to reduce disk spikes
- Add disk free-space fail-fast check

1) **Release retention policy (avoid disk blow-up)**
- Keep last N releases; never delete what `current` points to

2) **Backup/restore**
- Scripted backups for SQLite + key data dirs (pdf/mineru/gen/logs)
- Lightweight option: DB-only backup (derived artifacts can be recomputed)

3) **Config health checks**
- `/api/status` health checklist:
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
