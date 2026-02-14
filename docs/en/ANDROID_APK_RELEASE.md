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

### 6.1 Timestamped releases (audit-friendly)

```bash
TAG="android-YYYYMMDD-HHMMSS"
APK="papertok/exports/android/<your>.apk"
SHA="${APK}.sha256"

gh release create "$TAG" \
  --repo ViffyGwaanl/papertok \
  --title "PaperTok Android APK ($TAG)" \
  --notes "Internal build." \
  --prerelease \
  "$APK" "$SHA"
```

### 6.2 Stable “latest” download URL (strongly recommended)

Maintain a moving, **non-prerelease** tag `android-latest` and upload fixed-name assets:
- `papertok-android-latest.apk`
- `papertok-android-latest.apk.sha256`

This keeps a stable link for README/announcements:
- `https://github.com/ViffyGwaanl/papertok/releases/latest/download/papertok-android-latest.apk`

Update by overwriting assets (same release, same link):

```bash
TAG="android-latest"
APK_SRC="papertok/exports/android/<your>.apk"
SHA_SRC="${APK_SRC}.sha256"

cp "$APK_SRC" /tmp/papertok-android-latest.apk
cp "$SHA_SRC" /tmp/papertok-android-latest.apk.sha256

gh release upload "$TAG" \
  --repo ViffyGwaanl/papertok \
  --clobber \
  /tmp/papertok-android-latest.apk \
  /tmp/papertok-android-latest.apk.sha256
```

---

## 7) iCloud Drive pitfall (important)

If you keep APKs under iCloud Drive (e.g. `~/Library/Mobile Documents/...`), some automation/background contexts may fail to read them with:
- `OSError: [Errno 11] Resource deadlock avoided`

Workaround: copy the APK to a non-iCloud local directory (e.g. `/tmp/` or `~/Downloads/`) before `gh release upload`.

---

## 8) Remember to bump versionCode
Edit (prefer the kts file):
- `papertok/frontend/wikitok/frontend/android/app/build.gradle.kts` (or legacy `build.gradle`)

Rules:
- Every release: `versionCode` must increase.
- `versionName` is for humans.

---

## 9) Receiver-side notes
- First install: allow “unknown sources”.
- If signature mismatch (debug vs release): uninstall old build first.

---

## 10) Optional: use AAB for Google Play

```bash
cd papertok/frontend/wikitok/frontend/android
./gradlew bundleRelease
```

APK is still best for direct installs.
