#!/usr/bin/env bash
set -euo pipefail

# Install / update cloudflared watchdog LaunchAgent:
# - com.papertok.cloudflared_watchdog

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="$ROOT_DIR/ops/launchd"
DST_DIR="$HOME/Library/LaunchAgents"

DEFAULT_PREFIX="/Users/gwaanl/.openclaw/workspace/papertok"

mkdir -p "$DST_DIR"

f="com.papertok.cloudflared_watchdog.plist"
src="$SRC_DIR/$f"
dst="$DST_DIR/$f"

# Render plist paths for current checkout.
sed "s#${DEFAULT_PREFIX}#${ROOT_DIR}#g" "$src" > "$dst"

launchctl unload "$dst" 2>/dev/null || true
launchctl load "$dst"
launchctl kickstart -k "gui/$(id -u)/com.papertok.cloudflared_watchdog" || true

echo "OK: installed $f to $DST_DIR"
