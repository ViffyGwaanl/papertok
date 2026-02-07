#!/usr/bin/env bash
set -euo pipefail

# Install / update ONLY the recommended core LaunchAgents:
# - com.papertok.server
# - com.papertok.daily
# - com.papertok.job_worker
# - com.papertok.logrotate

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="$ROOT_DIR/ops/launchd"
DST_DIR="$HOME/Library/LaunchAgents"

# The repo plists include an absolute path from the original dev machine.
# Render them for THIS machine by replacing that prefix.
DEFAULT_PREFIX="/Users/gwaanl/.openclaw/workspace/papertok"

mkdir -p "$DST_DIR"

core=(
  com.papertok.server.plist
  com.papertok.daily.plist
  com.papertok.job_worker.plist
  com.papertok.logrotate.plist
)

for f in "${core[@]}"; do
  src="$SRC_DIR/$f"
  dst="$DST_DIR/$f"

  # Render plist paths for current checkout.
  sed "s#${DEFAULT_PREFIX}#${ROOT_DIR}#g" "$src" > "$dst"

  launchctl unload "$dst" 2>/dev/null || true
  launchctl load "$dst"
done

# Start server + worker immediately; daily/logrotate will run on schedule.
launchctl kickstart -k "gui/$(id -u)/com.papertok.server" || true
launchctl kickstart -k "gui/$(id -u)/com.papertok.job_worker" || true

echo "OK: installed core LaunchAgents to $DST_DIR"
