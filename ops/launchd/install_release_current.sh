#!/usr/bin/env bash
set -euo pipefail

# Install/update LaunchAgents that point to DEPLOY_ROOT/current/... (release-based deployment)

DEPLOY_ROOT="${PAPERTOK_DEPLOY_ROOT:-$HOME/papertok-deploy}"
CURRENT="$DEPLOY_ROOT/current"

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/release"
DST_DIR="$HOME/Library/LaunchAgents"

PLACEHOLDER_PREFIX="/Users/gwaanl/papertok-deploy/current"
REAL_PREFIX="$CURRENT"

mkdir -p "$DST_DIR"

agents=(
  com.papertok.server.plist
  com.papertok.daily.plist
  com.papertok.job_worker.plist
  com.papertok.logrotate.plist
  com.papertok.cloudflared_watchdog.plist
)

for f in "${agents[@]}"; do
  src="$SRC_DIR/$f"
  dst="$DST_DIR/$f"
  if [[ ! -f "$src" ]]; then
    echo "WARN: missing template $src" >&2
    continue
  fi

  sed "s#${PLACEHOLDER_PREFIX}#${REAL_PREFIX}#g" "$src" > "$dst"
  launchctl unload "$dst" 2>/dev/null || true
  launchctl load "$dst"
done

echo "OK: installed release-based LaunchAgents (DEPLOY_ROOT=$DEPLOY_ROOT)"
