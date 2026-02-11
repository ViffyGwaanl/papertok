# Android APK Release (Distribution)

[English](./ANDROID_APK_RELEASE.md) | [中文](../ANDROID_APK_RELEASE.md)

> Goal: build a **signed release** APK that can be installed and upgraded over time.

---

## 1) Why a signed release APK is required
To upgrade via “install over existing” on Android:
1) Same `applicationId` (this project: `com.gwaanl.papertok`)
2) Same signing certificate (same keystore + alias)
3) `versionCode` must increase every release

If you lose the keystore, you cannot ship upgrades under the same package name.

---

## 2) One-time setup: create a keystore
Create it in a secure location (do NOT commit it):

```bash
keytool -genkeypair -v \
  -keystore papertok-release.keystore \
  -alias papertok \
  -keyalg RSA -keysize 2048 -validity 10000
```

Back it up (iCloud Drive / 1Password / encrypted USB, etc.).

---

## 3) One-time setup: provide signing params to Gradle
Recommended: put secrets in `~/.gradle/gradle.properties`:

```properties
PAPERTOK_STORE_FILE=/absolute/path/papertok-release.keystore
PAPERTOK_STORE_PASSWORD=...
PAPERTOK_KEY_ALIAS=papertok
PAPERTOK_KEY_PASSWORD=...
```

---

## 4) Prereqs (JDK/SDK)
- JDK 17 recommended
- Android SDK + Build-Tools

Verify:
```bash
java -version
```

---

## 5) Build command (one-liner)
From repo root:

```bash
cd papertok
bash ops/build_android_release_apk.sh
```

Outputs:
- `papertok/exports/android/*.apk`
- `papertok/exports/android/*.sha256`

---

## 6) Recommended distribution: GitHub Releases
Create a release and upload assets (APK + sha256).

Use the Releases page as the single source of truth for downloads:
- https://github.com/ViffyGwaanl/papertok/releases

Example:
```bash
TAG="android-YYYYMMDD-HHMMSS"
APK="papertok/exports/android/<your>.apk"
SHA="$APK.sha256"

gh release create "$TAG" \
  --repo ViffyGwaanl/papertok \
  --title "PaperTok Android APK ($TAG)" \
  --notes "Internal build." \
  --prerelease \
  "$APK" "$SHA"
```

### Important: iCloud Drive / File Provider directories
If your APK is under an iCloud Drive / File Provider managed path (e.g. `~/Library/Mobile Documents/...`), some background processes may fail to read the file contents and you may see:
- `OSError: [Errno 11] Resource deadlock avoided`

This can break `cp/ditto/gh release create` uploads.

Workaround: copy the `*.apk` and `*.sha256` to a local non-iCloud folder first (e.g. `~/Downloads/` or `papertok/exports/android/`), then upload.

---

## 7) Remember to bump versionCode
Edit: `papertok/frontend/wikitok/frontend/android/app/build.gradle`

```gradle
versionCode 1
versionName "1.0"
```

Rules:
- Every release: `versionCode` must increase.
- `versionName` is for humans.

---

## 8) Receiver-side notes
- First install: allow “unknown sources”.
- If signature mismatch (debug vs release): uninstall old build first.
