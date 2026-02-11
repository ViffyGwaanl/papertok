# PaperTok (MVP)

[English](./README.en.md) | [中文](./README.md)

Goal: run PaperTok locally — fetch Hugging Face Daily Papers **Top 10 of the day**, run the full offline pipeline (PDF → MinerU → explanation → image captions → vertical collage illustrations → one-liner), and browse with a WikiTok-style infinite vertical feed.

## Docs (recommended reading order)
- Handbook / Ops manual: `papertok/docs/Handbook.md`
- Project history (what’s already done): `papertok/docs/HISTORY.md`
- Roadmap (what’s next): `papertok/docs/ROADMAP.md`

## WeChat Official Account
**书同文Suwin**

![WeChat OA QR](docs/assets/mp_suwin_qr.jpg)

## Install (iOS / Android)

- **iOS (TestFlight)**
  - https://testflight.apple.com/join/cxaZq2jv

- **Android (APK sideload)**: download the latest `*.apk` from GitHub Releases
  - https://github.com/ViffyGwaanl/papertok/releases

> On Android, you may need to allow “Install unknown apps”. If you previously installed a build signed with a different keystore, uninstall the old app first.

## Current Status (What’s implemented)
- ✅ Backend: FastAPI + SQLite (SQLModel)
- ✅ Single-origin deployment: backend serves frontend `dist/` to avoid LAN/localhost/CORS issues
- ✅ Public ingress (no VPS): Cloudflare Tunnel → `https://papertok.ai/` (canonical)
- ✅ Domain canonicalization: `https://papertok.net/*` **301 redirect** to `https://papertok.ai/$1` (preserve path + query)
- ✅ Zero Trust: Cloudflare Access protects `/admin*` and `/api/admin*` (email allowlist)
- ✅ APIs:
  - `GET /healthz`
  - `GET /api/papers/random?limit=20` (history feed; supports `day=latest` or `day=YYYY-MM-DD`; also supports `lang=zh|en|both`)
  - `GET /api/papers/{id}` (detail modal: explanation / MinerU markdown / extracted images + captions / PDF / generated images)
  - `GET /api/status` (public status summary; no local paths/log paths)
  - `GET /api/public/status` (alias)
  - `GET /api/admin/status` (admin status; requires `X-Admin-Token` and should be protected by Cloudflare Access)
  - `GET/PUT /api/admin/config` (DB-backed runtime config; used by `/admin` UI)
- ✅ Pipeline (`backend/scripts/daily_run.py`):
  - HF Daily ingest (Top10 only; history is accumulated)
  - arXiv PDF download (`/static/pdfs`)
  - MinerU: PDF → markdown + extracted images (`/static/mineru`)
  - Explanations: teaching-style long explanation (ZH + EN)
  - Image captions: VLM captions for all extracted figures (ZH + EN)
  - Generated illustrations: vertical scrapbook/magazine collages (GLM-Image + optional second provider) stored in `paper_images` and served under `/static/gen*`
- ✅ PWA Service Worker fixed: `/static/*` won’t incorrectly fall back to SPA index
- ✅ Capacitor build mode (`vite --mode capacitor`) disables PWA/SW by default to avoid WebView caching issues
- ✅ Mobile/public-origin fix: frontend defaults to `window.location.origin` (no hard-coded `:8000`)
- ✅ iOS/Android internal build scaffold: Capacitor projects committed under `frontend/wikitok/frontend/ios` and `android` (Phase 1: use public `https://papertok.ai`)

## Components
- `backend/` FastAPI server
- `backend/scripts/` pipeline scripts / job handlers
- `frontend/` WikiTok-style UI
- `data/` local data dir (SQLite, PDFs, MinerU outputs, generated images, logs)

## Quick Start (single service: backend serves frontend)

1) Build frontend (`frontend/wikitok/frontend/dist/`)
```bash
cd frontend/wikitok/frontend
npm install
npm run build
```

2) Start backend (serves `dist/`)
```bash
cd backend
# Python 3.13 recommended on macOS
/opt/homebrew/bin/python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd ..
cp .env.example .env
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open: http://127.0.0.1:8000/

Admin: http://127.0.0.1:8000/admin

## LAN access (phone/other machines)
The server typically listens on `0.0.0.0:8000` (via launchd `com.papertok.server`).

1) Get LAN IP (macOS)
```bash
ipconfig getifaddr en0  # ethernet
ipconfig getifaddr en1  # Wi‑Fi
```

2) Open on the same Wi‑Fi:
`http://<LAN-IP>:8000/`

> If it keeps loading / assets don’t update, it’s often PWA cache. Try an incognito window or add `?v=3` to the URL.

---

Security note: do NOT commit any API keys. Put secrets only in `.env`.
