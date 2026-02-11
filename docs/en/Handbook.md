# PaperTok Handbook (Engineering Guide)

[English](./Handbook.md) | [中文](../Handbook.md)

> Version: 2026-02-11 (living document). Covers Cloudflare Tunnel/Access, canonical domains, mobile same-origin fixes, and the ZH/EN bilingual pipeline.

## 1) Overview

PaperTok is a locally deployed “papers TikTok/WikiTok” app:
- Canonical domain: `https://papertok.ai`
- Alias: `https://papertok.net` → **301** redirect to `papertok.ai` (preserve path + query)
- Daily ingest: Hugging Face Daily Papers **Top 10**
- Download arXiv PDFs
- Parse PDFs locally via **MinerU CLI** → markdown + extracted images
- Generate teaching-style explanations via LLM (ZH `content_explain` + EN `content_explain_en`)
- Generate figure captions via VLM (ZH `image_captions_json` + EN `image_captions_en_json`)
- Web UI supports content language toggle (`中文/EN`)
- Generate vertical scrapbook/magazine collage illustrations via **Seedream + GLM-Image**
- Backend: FastAPI provides APIs and serves the built frontend `dist/`

### 1.1 Goals
- Local-first: run long-term on a single Mac mini.
- Single-origin stability: backend serves frontend to avoid CORS/localhost issues.
- No long tasks in request path: heavy work goes to scripts / Jobs queue.
- No fake data: if MinerU/explanations fail, skip; feed is gated to “complete items”.
- Operable & observable: Admin UI, job logs, `/api/status`, `paper_events`.

### 1.2 Non-goals (for now)
- Distributed queue/K8s
- Multi-user auth system
- Running MinerU as a remote service (currently local CLI)

---

## 2) Quick Start

### 2.1 Prerequisites
- macOS (launchd is used for daemons)
- Python (recommended 3.13)
- Node/npm (frontend build)
- MinerU CLI available (`backend/requirements.mineru.txt`)
- Optional: `qpdf` for conservative PDF repair on MinerU failures

### 2.2 One-time initialization
```bash
cd papertok
cp .env.example .env  # do NOT commit .env

cd backend
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# If needed: pip install -r requirements.mineru.txt

cd ../frontend/wikitok/frontend
npm install
npm run build
```

### 2.3 Start (recommended: Scheme B release deployment)
Production should use **Release-based Deployment (Scheme B)**: immutable releases + atomic `current` symlink.
- Doc: `docs/RELEASE_DEPLOYMENT.md`
- Install release-mode LaunchAgents: `ops/launchd/install_release_current.sh`

Check status:
```bash
launchctl list | rg com\.papertok
```

Endpoints:
- UI: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin`
- Health: `GET /healthz`

### 2.4 Run the full pipeline manually
```bash
cd papertok
bash ops/run_daily.sh
```

### 2.5 Backfill a specific HF day (optional)
Use `HF_DATE=YYYY-MM-DD` to ingest that day:
```bash
cd papertok
HF_DATE=2026-02-03 bash ops/run_daily.sh
```

If you only want ingest + PDF + MinerU (prepare the base) and let Jobs handle explain/caption/images later:
```bash
cd papertok
HF_DATE=2026-02-03 \
  RUN_CONTENT_ANALYSIS=0 RUN_IMAGE_CAPTION=0 RUN_PAPER_IMAGES=0 \
  SKIP_LLM=1 \
  bash ops/run_daily.sh
```

---

## 3) Architecture & Key Decisions

### 3.1 Single service (same origin)
- FastAPI mounts Vite `dist/` to `/`
- SPA deep links (`/admin`, `/admin/*`) fall back to `index.html`

### 3.2 Background processing: Jobs queue + worker
- Anything potentially minutes-long runs via DB `jobs` + `job_worker`
- Admin UI can enqueue jobs, list recent jobs, tail logs
- Worker runs via launchd every ~60s (Admin can also “Kick worker now”)

### 3.3 Two image providers
- `paper_images` stores generated images per provider (`seedream`/`glm`)
- Feed display provider is DB-configurable: `paper_images_display_provider`

### 3.4 “Complete feed” gating
Default DB config gates feed to only show items with:
- explanation
- captions
- generated images (for the display provider)

### 3.5 Conservative PDF repair
- Never mutate the original PDF
- Repair into `data/raw/pdfs_repaired/` only after MinerU fails

---

## 4) Storage & Data Model

### 4.1 Data directories
- `data/db/papertok.sqlite`
- `data/raw/pdfs/` → `/static/pdfs`
- `data/raw/pdfs_repaired/`
- `data/mineru/` → `/static/mineru`
- `data/gen_images/` (Seedream) → `/static/gen`
- `data/gen_images_glm/` (GLM) → `/static/gen_glm`
- `data/logs/`

### 4.2 Main tables (conceptual)
- `papers`: `day`, `pdf_path`, `raw_text_path`, `one_liner/one_liner_en`, `content_explain/content_explain_en`, `image_captions_json/image_captions_en_json`...
- `paper_images`: `kind`, `provider`, `lang`, `order_idx`, `url_path`...
- `paper_events`: stage-level observability
- `jobs`: background tasks
- `app_settings`: DB-backed runtime config

---

## 5) Configuration: .env vs DB config

### 5.1 Principle
- Secrets/paths/runtime environment → `.env` (gitignored)
- Runtime policy toggles → DB config (`app_settings`)

### 5.2 `.env` (single source of truth)
- Backend + ops scripts + launchd all read `papertok/.env`
- Template: `papertok/.env.example`

Common keys (excerpt):
- `OPENAI_BASE_URL`, `LLM_MODEL_TEXT`, `LLM_MODEL_ANALYSIS`
- `IMAGE_CAPTION_MODEL`
- `PAPERTOK_LANGS=zh,en`
- `PAPER_IMAGES_DISPLAY_PROVIDER` + `PAPER_IMAGES_GENERATE_ONLY_DISPLAY=1`
- `IMAGE_CAPTION_CONCURRENCY`

### 5.3 DB config (Admin)
- `feed_require_explain`
- `feed_require_image_captions`
- `feed_require_generated_images`
- `paper_images_display_provider`
- caption context parameters

---

## 6) APIs

### 6.1 Health
- `GET /healthz` → `{ok: true}`

### 6.2 Feed & paper detail
- `GET /api/papers/random?limit=20&lang=zh|en|both&day=latest|YYYY-MM-DD|all`
  - Language-aware gating (Strategy A): `lang=en` requires the EN chain to be complete; `lang=zh` requires the ZH chain.
- `GET /api/papers/{id}?lang=zh|en|both`

### 6.3 Status & ops observability
- Public:
  - `GET /api/status` (no local paths/log paths)
  - `GET /api/public/status` (alias)
- Admin:
  - `GET /api/admin/status` (requires `X-Admin-Token`, should be behind Cloudflare Access)

### 6.4 Admin (token-protected)
- `GET/PUT /api/admin/config`
- `GET /api/admin/jobs`
- `POST /api/admin/jobs/{job_type}`
- `GET /api/admin/jobs/{id}`
- `GET /api/admin/jobs/{id}/log?tail_lines=...`
- `POST /api/admin/jobs/worker/kick`

---

## 7) Pipeline & observability

Stages (conceptual):
1) HF ingest
2) PDF download
3) MinerU parse (+ repair-on-fail)
4) one-liner (ZH/EN)
5) explanation (ZH/EN)
6) captions (ZH/EN)
7) generated images (ZH/EN, providers)

`paper_events` records started/success/failed/skipped per stage.

---

## 8) Admin / Jobs / Worker

- Jobs are stored in DB, with per-job log files under `data/logs/job_<id>_<type>.log`.

Supported job types (excerpt):
- `one_liner_scoped`, `one_liner_regen_scoped`
- `content_analysis_scoped`, `content_analysis_regen_scoped`
- `image_caption_scoped`, `image_caption_regen_scoped`
- `paper_images_scoped`, `paper_images_regen_scoped`
- `paper_events_backfill`
- `paper_retry_stage`

---

## 9) launchd & log rotation (macOS)
Core daemons:
- `com.papertok.server`
- `com.papertok.job_worker`
- `com.papertok.daily`
- `com.papertok.logrotate`

---

## 10) Security boundary (LAN + public)
See `docs/SECURITY.md`.

---

## 11) Troubleshooting
- Feed empty: check feed gating in `/admin`.
- MinerU PDFium data format error: install `qpdf`, enable repair-on-fail.
- Frontend update not visible: PWA/SW cache; try incognito, hard reload, or `?v=...`.
- Stuck running job: avoid killing the worker; inspect job logs and retry via Admin.

Appendix:
- `/api/status`, `data/logs/`, `/admin`
