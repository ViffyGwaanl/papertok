#!/usr/bin/env bash
set -euo pipefail

BASE_PUBLICS_RAW="${PAPERTOK_PUBLIC_BASE_URLS:-${PAPERTOK_PUBLIC_BASE_URL:-https://papertok.ai}}"
BASE_LOCAL="${PAPERTOK_LOCAL_BASE_URL:-http://127.0.0.1:8000}"

# Parse comma-separated list into array
IFS=',' read -r -a BASE_PUBLICS <<< "${BASE_PUBLICS_RAW}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

hdr() {
  # print response headers (no body)
  curl -sS -D- -o /dev/null "$1"
}

echo "== PaperTok security smoke =="
echo "public: ${BASE_PUBLICS_RAW}"
echo "local : ${BASE_LOCAL}"
echo

# 1) Cloudflare Access should protect admin surfaces (public)
echo "[1] Cloudflare Access gating (public)"
for BASE_PUBLIC in "${BASE_PUBLICS[@]}"; do
  BASE_PUBLIC="${BASE_PUBLIC%/}"
  echo "-- ${BASE_PUBLIC}"

  H1="$(hdr "${BASE_PUBLIC}/admin" | head -n 30)"
  echo "$H1" | head -n 5
  echo "$H1" | grep -qiE '^location: https://.*cloudflareaccess\.com/' || fail "${BASE_PUBLIC}/admin not gated by Cloudflare Access"

  H2="$(hdr "${BASE_PUBLIC}/api/admin/config" | head -n 30)"
  echo "$H2" | head -n 5
  echo "$H2" | grep -qiE '^location: https://.*cloudflareaccess\.com/' || fail "${BASE_PUBLIC}/api/admin/config not gated by Cloudflare Access"

  H3="$(hdr "${BASE_PUBLIC}/api/admin/status" | head -n 30)"
  echo "$H3" | head -n 5
  echo "$H3" | grep -qiE '^location: https://.*cloudflareaccess\.com/' || fail "${BASE_PUBLIC}/api/admin/status not gated by Cloudflare Access"

  echo
done

# 2) Local admin API must require X-Admin-Token
echo "[2] Local admin token enforcement"
H4="$(hdr "${BASE_LOCAL}/api/admin/config" | head -n 20)"
echo "$H4" | head -n 5
echo "$H4" | head -n 1 | grep -qE ' 401 ' || fail "local /api/admin/config should be 401 without X-Admin-Token"

echo

# 3) Public endpoints must not leak absolute paths or operational log paths
echo "[3] Public info-leak regression"
for BASE_PUBLIC in "${BASE_PUBLICS[@]}"; do
  BASE_PUBLIC="${BASE_PUBLIC%/}"
  echo "-- ${BASE_PUBLIC}"

  PAPER_JSON="$(curl -sS "${BASE_PUBLIC}/api/papers/18" | head -c 200000)"
  echo "$PAPER_JSON" | grep -qE '/Users/|raw_text_path' && fail "${BASE_PUBLIC}/api/papers/{id} leaks local path" || true

  STATUS_JSON="$(curl -sS "${BASE_PUBLIC}/api/status" | head -c 200000)"
  echo "$STATUS_JSON" | grep -qE '/Users/|log_path' && fail "${BASE_PUBLIC}/api/status leaks local path/log_path" || true

  STATUS_PUBLIC_JSON="$(curl -sS "${BASE_PUBLIC}/api/public/status" | head -c 200000)"
  echo "$STATUS_PUBLIC_JSON" | grep -qE '/Users/|log_path' && fail "${BASE_PUBLIC}/api/public/status leaks local path/log_path" || true

done

echo "OK"
