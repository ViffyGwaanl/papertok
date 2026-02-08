#!/usr/bin/env bash
set -euo pipefail

# Build a SIGNED Android release APK for distribution.
# Output: papertok/exports/android/*.apk (+ .sha256)
#
# Prereqs (one-time): configure release signing properties (see docs).

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FE="$ROOT/frontend/wikitok/frontend"
ANDROID="$FE/android"
OUTDIR="$ROOT/exports/android"

mkdir -p "$OUTDIR"

echo "== PaperTok Android release APK build =="
echo "root   : $ROOT"
echo "frontend: $FE"
echo "android : $ANDROID"
echo "out    : $OUTDIR"
echo

cd "$FE"

if [[ ! -d node_modules ]]; then
  echo "[1/3] Installing npm dependencies (node_modules missing)"
  npm install
fi

echo "[2/3] Build web + sync Capacitor android"
npm run cap:sync:android

echo "[3/3] Gradle assembleRelease"

# Sanity check: Java runtime
JAVA_V="$(java -version 2>&1 || true)"
if echo "$JAVA_V" | grep -q "Unable to locate a Java Runtime"; then
  echo "ERROR: Java runtime not found. Gradle requires a JDK to build APKs."
  echo "Fix (pick one):"
  echo "  - Install JDK 17 (recommended on macOS): brew install --cask temurin@17"
  echo "  - Or set JAVA_HOME to a valid JDK (e.g. Android Studio embedded JDK)"
  exit 2
fi

cd "$ANDROID"
./gradlew --no-daemon assembleRelease

APK="$ANDROID/app/build/outputs/apk/release/app-release.apk"
UNSIGNED="$ANDROID/app/build/outputs/apk/release/app-release-unsigned.apk"

if [[ -f "$APK" ]]; then
  SRC="$APK"
elif [[ -f "$UNSIGNED" ]]; then
  echo "ERROR: Release APK is unsigned: $UNSIGNED"
  echo "Fix: configure signing (PAPERTOK_STORE_FILE / PAPERTOK_STORE_PASSWORD / PAPERTOK_KEY_ALIAS / PAPERTOK_KEY_PASSWORD)"
  exit 2
else
  echo "ERROR: APK not found under app/build/outputs/apk/release/"
  exit 2
fi

# Extract versionName/versionCode from android/app/build.gradle (best-effort)
BG="$ANDROID/app/build.gradle"
VER_NAME="$(sed -nE 's/^\s*versionName\s+"([^"]+)"\s*$/\1/p' "$BG" | head -n 1)"
VER_CODE="$(sed -nE 's/^\s*versionCode\s+([0-9]+)\s*$/\1/p' "$BG" | head -n 1)"
TS="$(date +"%Y%m%d-%H%M%S")"

NAME="papertok"
if [[ -n "${VER_NAME}" && -n "${VER_CODE}" ]]; then
  NAME+="-v${VER_NAME}(${VER_CODE})"
else
  NAME+="-${TS}"
fi

DEST="$OUTDIR/${NAME}-${TS}.apk"
cp -f "$SRC" "$DEST"

# checksum
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$DEST" | tee "$DEST.sha256" >/dev/null
elif command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$DEST" | tee "$DEST.sha256" >/dev/null
fi

BYTES="$(wc -c < "$DEST" | tr -d ' ')"
echo

echo "OK"
echo "APK     : $DEST"
echo "Size    : ${BYTES} bytes"
echo "Checksum: $DEST.sha256"
