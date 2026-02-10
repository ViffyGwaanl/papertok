#!/usr/bin/env bash
set -euo pipefail

# Atomically switch DEPLOY_ROOT/current to a given release id and restart services.
#
# Usage:
#   ops/release/switch_current.sh <release-id>

DEPLOY_ROOT="${PAPERTOK_DEPLOY_ROOT:-$HOME/papertok-deploy}"
REL_ID="${1:-}"
if [[ -z "$REL_ID" ]]; then
  echo "Usage: $0 <release-id>" >&2
  exit 2
fi

REL_DIR="$DEPLOY_ROOT/releases/$REL_ID"
if [[ ! -d "$REL_DIR" ]]; then
  echo "ERROR: release not found: $REL_DIR" >&2
  exit 1
fi

ln -sfn "$REL_DIR" "$DEPLOY_ROOT/current"
echo "OK: current -> $REL_DIR"

UID="$(id -u)"

# Restart core services to pick up new code.
# Note: cloudflared tunnel itself is independent; we only restart app services.
launchctl kickstart -k "gui/$UID/com.papertok.server" || true
launchctl kickstart -k "gui/$UID/com.papertok.job_worker" || true

# daily/logrotate are scheduled; watchdog is optional
launchctl kickstart -k "gui/$UID/com.papertok.cloudflared_watchdog" 2>/dev/null || true

# Smoke check
sleep 2
curl -fsS --max-time 5 http://127.0.0.1:8000/healthz >/dev/null && echo "OK: healthz"
