# PaperTok iOS App Plan (Phase 1: Public HTTPS Only)

[English](./IOS_APP_PLAN.md) | [中文](../IOS_APP_PLAN.md)

> Goal: package the existing React/Vite frontend into an installable iPhone app using **Capacitor** (internal build).
> Phase 1 uses only the public canonical domain `https://papertok.ai` (with `papertok.net` as a 301 alias), and does not do LAN direct access.
>
> Status: ✅ validated on a real iPhone via Xcode (internal build).

---

## 0) Scope & non-goals

### 0.1 In scope
- Install/run on a real iPhone (internal build)
- Feature loop:
  - Vertical feed (`/api/papers/random`)
  - Detail modal: explanation / MinerU markdown / extracted images + captions (`/api/papers/{id}` + `/static/*`)
  - Open arXiv PDF (external link)
  - Share paper link
- Network: public HTTPS only (`https://papertok.ai`)

### 0.2 Out of scope
- LAN direct access (HTTP/HTTPS)
- Login/accounts
- Push notifications
- Admin inside the app
- App Store release (not DoD for this phase)

---

## 1) Security boundary
- App calls only public endpoints:
  - `/healthz`, `/api/papers/*`, `/api/status` (public), `/static/*`
- App must not call/expose:
  - `/admin*`, `/api/admin*`
- App must not store admin secrets
- Public data-leak baseline must hold (`ops/security_smoke.sh`)

---

## 2) Technical approach
- Shell: Capacitor (iOS WebView)
- Web code: React + Vite
- Plugins (as needed): Browser, Share, Preferences

---

## 3) Engineering changes for stability

### 3.1 API base single source of truth
- `src/lib/apiBase.ts`
- In this phase: `VITE_API_BASE=https://papertok.ai` (avoid `papertok.net` to reduce redirects)

### 3.2 Service Worker in WebView
In capacitor build mode (`vite --mode capacitor`), PWA is disabled to avoid SW caching surprises.

---

## 4) Milestones (WBS)

### Phase 0: inputs
- Bundle ID
- Whether you have Apple Developer Program (for TestFlight) or only Xcode local install

### Phase 1: Capacitor iOS MVP
- `npm run cap:sync:ios`
- `npm run cap:open:ios`
- Run on device

Acceptance:
- Feed loads
- Detail loads
- External PDF opens
- Share works

### Phase 2: stability & diagnosability
- Optional debug diagnostics page
- Better timeouts and error UI

### Phase 3: delivery & versioning
- Versioning rules
- Internal install doc

---

## 5) Test matrix (this phase)
- At least 1 main iPhone + (optional) another iOS version
- Wi‑Fi / 5G / weak network
- Long scrolling + repeated modal open/close

---

## 6) Next phase: LAN direct access
iOS has ATS restrictions for HTTP; consider LAN HTTPS for a cleaner approach.
