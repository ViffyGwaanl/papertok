# PaperTok Android App Plan (Phase 1: Public HTTPS Only)

[English](./ANDROID_APP_PLAN.md) | [中文](../ANDROID_APP_PLAN.md)

> Goal: package the existing React/Vite frontend into an Android app using **Capacitor** (internal build).
> Phase 1 uses only the public canonical domain `https://papertok.ai` (with `papertok.net` as a 301 alias).
>
> Status: ✅ validated on a real Android device via Android Studio (internal build).

---

## 0) Scope & non-goals

### 0.1 In scope (must deliver)
- Install/run on a real Android device (Android Studio Run; debug build)
- Feature loop:
  - Vertical feed (`/api/papers/random`)
  - Detail modal: explanation / MinerU markdown / extracted images + captions (`/api/papers/{id}` + `/static/*`)
  - Open arXiv PDF (external link)
  - Share paper link
- Network: public HTTPS only (`https://papertok.ai`)

### 0.2 Out of scope (not in this phase)
- LAN direct access (HTTP/HTTPS)
- Login/accounts/push notifications
- Admin inside the app
- Google Play store publishing

---

## 1) Security boundary (must follow)
- The app only calls public endpoints:
  - `/healthz`, `/api/papers/*`, `/api/status` (public summary), `/static/*`
- The app must NOT call/expose:
  - `/admin*`, `/api/admin*`
- The app must not store any admin secrets:
  - no `PAPERTOK_ADMIN_TOKEN`, no `X-Admin-Token`
- Run S0 security regression after changes: `ops/security_smoke.sh`

---

## 2) Engineering conventions
- API base single source of truth: `src/lib/apiBase.ts`
- Capacitor project: `papertok/frontend/wikitok/frontend/`
- Android project committed: `.../android/`
- Build mode: `vite build --mode capacitor`
- Public API base via `.env.capacitor`:
  - `VITE_API_BASE=https://papertok.ai`

Scripts:
- `npm run cap:sync:android`
- `npm run cap:open:android`

---

## 3) Install & run (developer machine)
```bash
git clone https://github.com/ViffyGwaanl/papertok.git
cd papertok/frontend/wikitok/frontend

npm install
npm run cap:sync:android
npm run cap:open:android
```
Then in Android Studio: select device → Run.

---

## 4) Acceptance checklist
- [ ] Feed loads (with images)
- [ ] Detail modal loads explain/markdown/images
- [ ] PDF external link opens
- [ ] Share works
- [ ] No Admin entry points

---

## 5) APK distribution
Use a **signed release APK** and distribute via GitHub Releases.
See: `docs/ANDROID_APK_RELEASE.md`.

---

## 6) Next phase: LAN direct access
Once public HTTPS is stable, add LAN (requires Android cleartext/networkSecurityConfig for HTTP, or LAN HTTPS).
