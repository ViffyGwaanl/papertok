# PaperTok iOS/Android App (Internal Build) – Implementation

[English](./MOBILE_APP_IMPLEMENTATION.md) | [中文](../MOBILE_APP_IMPLEMENTATION.md)

> This is the execution-oriented version of `docs/MOBILE_APP_PLAN.md`.
> Current assumption:
> - Internal distribution only (not in stores)
> - No login/push yet
> - Phase 1: public HTTPS only

---

## Current progress
- ✅ iOS: installed & running on a real iPhone via Xcode
- ✅ Android: installed & running on a real device via Android Studio

## 1) Tech stack
- Web: React + Vite
- App shell: Capacitor (iOS/Android WebView)
- Native capabilities (as needed): external links, share, local storage

## 2) Repo layout
Capacitor project is under `papertok/frontend/wikitok/frontend/`:
- `ios/`
- `android/`

Reason: Vite build outputs `dist/` here; Capacitor uses that as web assets.

## 3) API Base (single source of truth)
- `src/lib/apiBase.ts` is the only place to build API/asset URLs.
- In Capacitor WebView, origin is typically `capacitor://localhost`, so you must set `VITE_API_BASE` via `.env.capacitor`.

Phase 1:
- `VITE_API_BASE=https://papertok.ai` (canonical)

## 4) Capacitor steps
1) Install deps
2) Build (capacitor mode)
```bash
npm run build:capacitor
```
3) Sync
```bash
npm run cap:sync:ios
npm run cap:sync:android
```

**Important:** the app bundles the `dist/` assets at build time.
Any frontend feature update (e.g. ZH/EN toggle or UI i18n) requires re-sync and re-install / release a new build.

4) Open native projects
```bash
npm run cap:open:ios
npm run cap:open:android
```

5) Run on device via Xcode/Android Studio.

## 5) Distribution
- Android: debug APK (fast) or signed release APK (recommended for upgrades)
- iOS: TestFlight recommended (requires Apple Developer Program); otherwise Xcode install on your own device

## 6) Acceptance checklist
- Feed loads, detail modal works
- Captions and generated images render
- External links open
- Admin is not exposed in app builds (or only in internal builds behind Access + token)

## 7) Inputs to confirm
1) Bundle/package id preference
2) LAN access strategy (HTTP exceptions vs LAN HTTPS)
3) Whether you have Apple Developer Program for TestFlight
