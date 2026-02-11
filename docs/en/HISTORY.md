# PaperTok Project History (Done List)

[English](./HISTORY.md) | [中文](../HISTORY.md)

> Purpose: keep an auditable record of what has already been implemented.

## 0) Milestones
- M0: end-to-end MVP (HF Top10 → PDF → MinerU → explain → captions → images → FE)
- M1: Admin config (DB-backed)
- M2: Jobs queue + worker
- M3: Alembic migrations (schema evolution)
- M4: `paper_events` (observability + retry loop)
- P1 Ops: launchd consolidation + log rotation + relocatable paths
- Bilingual: ZH/EN full pipeline + API + UI toggle

---

## 1) Backend & frontend foundation
- FastAPI + SQLite (SQLModel)
- Single-origin service: backend serves built frontend `dist/`
- Static mounts:
  - `/static/mineru` → `MINERU_OUT_ROOT`
  - `/static/pdfs` → `PAPERS_PDF_DIR`
  - `/static/gen` → Seedream outputs
  - `/static/gen_glm` → GLM-Image outputs
- Frontend: vertical feed + detail modal (explain / markdown / extracted images + captions / PDF / generated images)

## 2) Data consistency & “No fake data”
- `papers.day` as partition key (YYYY-MM-DD)
- Feed gating via DB config to only show “complete” items

## 3) Two image providers (Seedream + GLM-Image)
- `paper_images` stores per-provider generated outputs
- Provider-aware uniqueness and feed display provider switch

## 4) Admin (DB-backed runtime config)
- `app_settings` table
- `GET/PUT /api/admin/config`
- Mobile-friendly `/admin` UI

## 5) Jobs system (background processing)
- `jobs` table + `job_worker`
- Admin APIs: enqueue/list/tail logs/kick worker
- Per-job log files: `data/logs/job_<id>_<type>.log`

## 6) `paper_events` (observability + retry loop)
- `paper_events` table for stage-level started/success/failed/skipped
- `/api/status` exposes aggregates and recent failures
- Per-paper retry to close the failure loop

## 7) PDF repair (conservative)
- Introduced `qpdf` repair cache directory `data/raw/pdfs_repaired/`
- Never mutates original PDFs

## 8) Alembic migrations (SQLite)
- Automatic migration on startup
- Baseline stamp support for legacy DBs

## 9) Ops on macOS (launchd + logs)
- Keep only core 4 daemons: server / job_worker / daily / logrotate
- Log rotation uses copy+truncate to avoid breaking long-running file descriptors

## 10) Public ingress
- Cloudflare Tunnel for `https://papertok.ai`
- Domain canonicalization: `papertok.net/*` → `papertok.ai/$1` (301)

## 11) Cloudflare Access + Admin token
- Access protects `/admin*` and `/api/admin*`
- Backend `PAPERTOK_ADMIN_TOKEN` requires `X-Admin-Token`

## 12) Mobile app (Capacitor internal build)
- Capacitor project committed under `frontend/wikitok/frontend/{ios,android}`
- `mode=capacitor` disables PWA/SW to avoid WebView caching surprises
- Runbook: `docs/APP_INTERNAL_RUNBOOK.md`

## 13) Android APK distribution
- Signed release APK script: `ops/build_android_release_apk.sh`
- Distribution via GitHub Releases with `.sha256`

## 14) Feed “complete item” gating (explain + captions + images)
- DB config: `feed_require_explain`, `feed_require_image_captions`, `feed_require_generated_images`

## 15) Scheme B deployment
- Releases under `~/papertok-deploy/releases/<id>`
- Active version via `~/papertok-deploy/current`

## 16) Dev environment (frozen dataset regression)
- Dev repo + shared state under `~/papertok-dev/...`
- Script: `ops/dev/run_full_pipeline_existing.sh`

## 17) ZH/EN bilingual full chain
- Schema: `one_liner_en`, `content_explain_en`, `image_captions_en_json`, `paper_images.lang`
- API: `lang=zh|en|both` for feed and detail; language-aware gating (Strategy A)
- Pipeline + Jobs: one-liner/explain/caption/images support `lang`
- Web UI: `中文/EN` toggle + UI i18n improvements

## 18) Backfill orchestration: last-7-days bilingual convergence + per-day acceptance monitor
- Enqueue script: `ops/backfill/run_bilingual_backfill_last7_days.sh`
- Acceptance monitor: `ops/backfill/monitor_day_completion.py`
  - strict 8-metric criteria (zh/en liner, zh/en explain, zh/en captions, glm/seedream images totals)
  - only prints when a day is complete; uses a state file to avoid duplicate reports

## 19) Android release distribution (GitHub Releases)
- Published internal build APKs via `gh release create` (APK + `.sha256`)
- Documented macOS iCloud Drive/File Provider limitation:
  - files under `~/Library/Mobile Documents/...` may raise `Resource deadlock avoided` for background reads
  - workaround: copy assets to a local non-iCloud folder (e.g. `~/Downloads/` or `exports/android/`) before uploading

## 20) Native-app-friendly language toggle fix
- Fixed the case where the feed card one-liner stayed in the previous language after switching.
- Key ideas: reset feed on language switch + generation-aware in-flight request handling + lang-scoped offline cache keys.

---

_Last updated: 2026-02-11_
