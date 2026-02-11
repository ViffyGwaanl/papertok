# PaperTok App Internal Runbook (iOS/Android)

[English](./APP_INTERNAL_RUNBOOK.md) | [中文](../APP_INTERNAL_RUNBOOK.md)

> Purpose: reproduce iOS/Android installs from a fresh clone.
> Current phase: public HTTPS only (canonical `https://papertok.ai`).

---

## 1) Prerequisites
- Node/npm
- Android Studio + Android SDK
- Xcode (for iOS)

Repo: https://github.com/ViffyGwaanl/papertok

Frontend directory:
```bash
cd papertok/frontend/wikitok/frontend
```

Install deps:
```bash
npm install
```

Build and sync native projects:
```bash
npm run cap:sync:ios
npm run cap:sync:android
```

**Important:** the app shell bundles the `dist/` assets at build time.
Web updates do **not** automatically update already-installed apps.
To get new features (e.g. the `中文/EN` toggle), you must rebuild and reinstall / publish a new APK/TestFlight build.

---

## 2) iOS (no paid dev program: install via Xcode to your own iPhone)
Limitations: Personal Team signing often expires in ~7 days; re-run from Xcode.

Steps:
1) Connect iPhone via cable
2) Enable Developer Mode (iOS 16+) and trust the computer
3) Open Xcode project:
```bash
npm run cap:open:ios
```
4) In Xcode → Signing & Capabilities:
- Select your Apple ID team
- If bundle id conflicts, change it (e.g. `com.gwaanl.papertok.ios`)
5) Select device → Run

---

## 3) Android (run via Android Studio)
If you want to distribute an APK to others, see: `docs/ANDROID_APK_RELEASE.md`.

### 3.1 Install SDK components (once)
In Android Studio SDK Manager, install:
- Android SDK Platform (e.g. API 34)
- Build-Tools (e.g. 34.x)
- Platform-Tools (includes `adb`)
- Command-line Tools (latest) (recommended)

If `adb` is missing:
- temporary: `~/Library/Android/sdk/platform-tools/adb devices`
- or add to PATH in `~/.zshrc`:
  - `export PATH="$HOME/Library/Android/sdk/platform-tools:$PATH"`

### 3.2 Open and run
```bash
npm run cap:open:android
```
Then Gradle sync and Run.

---

## 4) Troubleshooting

### 4.1 App loads forever / blank
Verify:
- `https://papertok.ai/healthz`
- `https://papertok.ai/api/status`

Ensure Capacitor build reads `.env.capacitor`:
- `VITE_API_BASE=https://papertok.ai`

### 4.2 iOS signing errors
- Ensure Xcode is logged into Apple ID
- Re-select team
- Ensure iPhone is in Developer Mode

### 4.3 Android Gradle/SDK issues
- Install missing SDK components via SDK Manager
- First Gradle import may be slow
