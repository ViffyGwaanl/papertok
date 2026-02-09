#!/usr/bin/env bash
set -euo pipefail

# Cloudflared tunnel watchdog for PaperTok.
#
# Purpose:
# - Detect the "cloudflared is running but tunnel has 0 active connections" state.
# - Self-heal by kickstarting the LaunchAgent com.papertok.cloudflared.
#
# Policy (defaults):
# - Require N consecutive failures before restart (default: 5)
# - Cooldown between restarts (default: 30 min)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data"
LOG_DIR="$DATA_DIR/logs"
mkdir -p "$LOG_DIR"

STATE_FILE="$DATA_DIR/.cloudflared_watchdog_state.json"
LOCK_DIR="$DATA_DIR/.cloudflared_watchdog.lock"

CLOUDFLARED_BIN="${CLOUDFLARED_BIN:-/opt/homebrew/bin/cloudflared}"
TUNNEL_NAME="${PAPERTOK_TUNNEL_NAME:-papertok-mac}"

FAILS_REQUIRED="${CLOUDFLARED_WATCHDOG_FAILS_REQUIRED:-5}"
COOLDOWN_SECONDS="${CLOUDFLARED_WATCHDOG_COOLDOWN_SECONDS:-1800}"

# log helper
log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_DIR/cloudflared_watchdog.log" >/dev/null
}

# simple non-blocking lock
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  # Another run in progress.
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

now_epoch="$(date +%s)"

# load state
state_json="$STATE_FILE"
if [[ ! -f "$state_json" ]]; then
  echo '{"consecutive_failures":0,"last_restart":0,"last_ok":0}' > "$state_json"
fi

read_state() {
  /usr/bin/python3 - "$STATE_FILE" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
try:
    obj=json.loads(p.read_text())
except Exception:
    obj={"consecutive_failures":0,"last_restart":0,"last_ok":0}
print(int(obj.get("consecutive_failures",0)))
print(int(obj.get("last_restart",0)))
print(int(obj.get("last_ok",0)))
PY
}

write_state() {
  local failures="$1"; local last_restart="$2"; local last_ok="$3"
  /usr/bin/python3 - "$STATE_FILE" "$failures" "$last_restart" "$last_ok" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
failures=int(sys.argv[2])
last_restart=int(sys.argv[3])
last_ok=int(sys.argv[4])
obj={
  "consecutive_failures": failures,
  "last_restart": last_restart,
  "last_ok": last_ok,
}
p.write_text(json.dumps(obj, ensure_ascii=False))
PY
}

IFS=$'\n' read -r failures last_restart last_ok <<EOF
$(read_state)
EOF
failures="${failures:-0}"
last_restart="${last_restart:-0}"
last_ok="${last_ok:-0}"

# determine tunnel connection health
if [[ ! -x "$CLOUDFLARED_BIN" ]]; then
  log "ERROR cloudflared binary not found: $CLOUDFLARED_BIN"
  exit 0
fi

info_out=""
info_rc=0
info_out="$($CLOUDFLARED_BIN tunnel info "$TUNNEL_NAME" 2>&1)" || info_rc=$?

# Count active connector rows in the table.
# Example rows start with UUID.
connector_count="$(printf '%s' "$info_out" | /usr/bin/python3 -c 'import re,sys
text=sys.stdin.read()
if "does not have any active connection" in text:
    print(0)
    raise SystemExit
pat=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\s", re.M)
print(len(pat.findall(text)))
')" || connector_count=0

if [[ -z "$connector_count" ]]; then connector_count=0; fi

if [[ "$connector_count" -gt 0 ]]; then
  # OK
  failures=0
  last_ok="$now_epoch"
  write_state "$failures" "$last_restart" "$last_ok"
  exit 0
fi

# Not OK: no active connection
failures=$((failures + 1))
log "WARN no active tunnel connection (failures=$failures rc=$info_rc)"

# restart if threshold reached and cooldown passed
since_restart=$((now_epoch - last_restart))
if [[ "$failures" -ge "$FAILS_REQUIRED" ]] && [[ "$since_restart" -ge "$COOLDOWN_SECONDS" ]]; then
  uid="$(id -u)"
  log "ACTION kickstart cloudflared (failures=$failures cooldown_ok=true)"
  launchctl kickstart -k "gui/$uid/com.papertok.cloudflared" || true
  last_restart="$now_epoch"
  failures=0
fi

write_state "$failures" "$last_restart" "$last_ok"
