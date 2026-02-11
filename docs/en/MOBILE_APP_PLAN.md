# Engineering Plan: Turn PaperTok Frontend into iOS/Android Apps

[English](./MOBILE_APP_PLAN.md) | [中文](../MOBILE_APP_PLAN.md)

Background: the frontend is React + Vite (WikiTok-style vertical feed). The FastAPI backend serves `dist/` (single origin), and web builds can use PWA (Service Worker).

Goal: productize the existing frontend into mobile apps (iOS/Android) with minimal cost, maximum code reuse, and a maintainable release pipeline.

---

## 0) Confirmed product decisions
- Distribution: internal (iOS TestFlight / internal builds; Android APK / internal tracks)
- Login: not needed (for now)
- Push: not needed
- Network strategy:
  - **Phase 1 (current)**: public HTTPS only via Cloudflare: `https://papertok.ai` (canonical; `papertok.net` 301 alias)
  - **Phase 2 (optional)**: add LAN direct access for faster local testing

Current progress:
- ✅ Capacitor iOS/Android projects generated and committed
- ✅ Installed and running on real devices via Xcode / Android Studio

---

## 1) Goals & scope

### Business goals
- App-like experience: full-screen vertical browsing, stable interactions
- Reliable network access via public domain
- Optional: offline browsing of previously loaded content
- Optional: share/open PDF/likes

### Technical goals
- Maximize reuse of current web code (React/Vite)
- Build a sustainable release pipeline (versioning, signing, testing)

Non-goals (short term)
- Full native rewrite
- Complex auth system

---

## 2) Options (cost vs benefit)

### Option A: PWA (lowest cost)
Pros: almost no extra engineering; instant updates.
Cons: iOS limitations; store distribution constraints.

### Option B: Capacitor (recommended)
Pros: reuse web code; can integrate native plugins; can ship as real apps.
Cons: still WebView; needs performance tuning for heavy media.

### Option C: React Native / Flutter rewrite (high cost)
Pros: more native control.
Cons: large rewrite and maintenance.

Recommended path: **A → B → (optional) LAN support → store readiness**.

---

## 3) Architecture & engineering changes

### 3.1 API base: single source of truth
To prevent partial failures (feed works but modal fails), keep API base in one module:
- `src/lib/apiBase.ts`

Phase 1:
- `VITE_API_BASE=https://papertok.ai` via `.env.capacitor`

Phase 2 (optional LAN):
- add LAN/public probing + manual override
- iOS ATS and Android cleartext policies must be handled

### 3.2 Admin and auth boundary
- Normal users should never access `/admin` or `/api/admin/*`
- If you ever expose admin in app (internal/debug only): still require Access + `X-Admin-Token`

### 3.3 Performance
- Lazy-load images
- Avoid blocking on image preloads
- Load markdown/details on demand

### 3.4 Offline strategy (optional)
- MVP: cache frontend assets
- Next: cache recent paper details

---

## 4) Milestones (WBS)

- Phase 0: requirements confirmation (done)
- Phase 1: PWA UX polish
- Phase 2: Capacitor MVP (done)
- Phase 3: store readiness (optional)
- Phase 4: enhancements (push/offline/accounts)

---

## 5) Quality & tests
- iOS: Safari (PWA) + Capacitor WebView
- Android: Chrome (PWA) + Capacitor WebView
- Wi‑Fi / 5G / weak network
- Metrics: first paint time, scroll smoothness, memory growth
