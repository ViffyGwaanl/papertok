#!/usr/bin/env bash
set -euo pipefail

# Rotate logs under papertok/data/logs.
# IMPORTANT: use copy+truncate (not rename) so launchd-managed processes keep writing to the same file handle.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/data/logs"

MAX_BYTES=${PAPERTOK_LOGROTATE_MAX_BYTES:-20000000}  # 20MB
KEEP=${PAPERTOK_LOGROTATE_KEEP:-10}

mkdir -p "$LOG_DIR"

_now_ts() {
  date +%Y%m%d-%H%M%S
}

_size_bytes() {
  # macOS stat
  stat -f %z "$1"
}

_rotate_one() {
  local f="$1"
  local base
  base=$(basename "$f")

  local sz
  sz=$(_size_bytes "$f" 2>/dev/null || echo 0)

  if [ "$sz" -lt "$MAX_BYTES" ]; then
    return 0
  fi

  local ts
  ts=$(_now_ts)
  local out="$LOG_DIR/${base}.${ts}"

  # Copy current log to archive, then truncate IN PLACE.
  # This avoids breaking stdout/stderr handles for long-running launchd jobs.
  cp -f "$f" "$out" || true
  : > "$f"

  gzip -f "$out" || true

  # Keep only newest $KEEP archives for this base
  # shellcheck disable=SC2012
  local archives
  archives=$(ls -1t "$LOG_DIR/${base}."*.gz 2>/dev/null || true)
  if [ -n "$archives" ]; then
    echo "$archives" | tail -n +$((KEEP+1)) | while read -r old; do
      [ -n "$old" ] && rm -f "$old" || true
    done
  fi

  echo "ROTATED: $base (${sz} bytes)"
}

for f in "$LOG_DIR"/*.log; do
  [ -f "$f" ] || continue
  _rotate_one "$f"
done
