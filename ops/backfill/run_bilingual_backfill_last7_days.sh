#!/usr/bin/env bash
set -euo pipefail

# Backfill last 7 HF daily days in DB for BOTH languages (zh+en):
# - one-liner
# - explanation (content_analysis)
# - image captions (VLM)
# - generated images (GLM display provider)
# - generated images (Seedream provider, fill missing)
#
# This script enqueues jobs only. The job_worker will execute them.
#
# Requirements:
# - papertok/.env exists and contains PAPERTOK_ADMIN_TOKEN
# - server is running on localhost:8000 (or set PAPERTOK_ADMIN_BASE)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "ERROR: $ROOT_DIR/.env not found" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

BASE="${PAPERTOK_ADMIN_BASE:-http://127.0.0.1:8000}"
TOKEN="${PAPERTOK_ADMIN_TOKEN:-}"

if [[ -z "$TOKEN" ]]; then
  echo "ERROR: PAPERTOK_ADMIN_TOKEN is empty; cannot enqueue admin jobs" >&2
  exit 1
fi

# Resolve DB path from DB_URL if possible.
DB_PATH=""
if [[ "${DB_URL:-}" == sqlite:////* ]]; then
  DB_PATH="/${DB_URL#sqlite:////}"
fi
if [[ -z "$DB_PATH" ]]; then
  # Fallback to default deploy path (works in Scheme B)
  DB_PATH="$HOME/papertok-deploy/shared/data/db/papertok.sqlite"
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "ERROR: DB not found: $DB_PATH" >&2
  exit 1
fi

mapfile -t DAYS < <(
  sqlite3 "$DB_PATH" "select day from papers where source='hf_daily' and day is not null group by day order by day desc limit 7;"
)

if [[ ${#DAYS[@]} -eq 0 ]]; then
  echo "ERROR: no hf_daily days found in DB" >&2
  exit 1
fi

# Process oldest -> newest (sqlite query returns newest first)
REV=()
for ((i=${#DAYS[@]}-1; i>=0; i--)); do
  REV+=("${DAYS[i]}")
done
DAYS=("${REV[@]}")

python3 - <<'PY'
import os
from datetime import datetime
print('Backfill plan (last 7 days in DB):')
PY
for d in "${DAYS[@]}"; do
  echo "- $d"
done

echo

enqueue(){
  local job_type="$1"
  local payload_json="$2"
  curl -sS -H "x-admin-token: $TOKEN" -H 'content-type: application/json' \
    -X POST "$BASE/api/admin/jobs/$job_type" \
    -d "$payload_json" \
    | python3 -c 'import sys,json; j=json.load(sys.stdin); job=j.get("job") or {}; print(job.get("id"))'
}

echo "Enqueueing jobs...";

declare -a JOB_IDS

# Tunables requested by user
CAPTION_CONCURRENCY=${CAPTION_CONCURRENCY:-8}
EXPLAIN_CONCURRENCY=${EXPLAIN_CONCURRENCY:-4}
IMAGES_CONCURRENCY=${IMAGES_CONCURRENCY:-4}
PER_PAPER_IMAGES=${PER_PAPER_IMAGES:-3}

# Ensure captions process all extracted images
CAPTION_MAX=${CAPTION_MAX:-100000}
CAPTION_PER_PAPER=${CAPTION_PER_PAPER:-100000}

# Ensure we don't accidentally skip day with >10 papers
MAX_PAPERS=${MAX_PAPERS:-50}

for d in "${DAYS[@]}"; do
  echo
  echo "=== day=$d ==="

  jid1=$(enqueue one_liner_scoped "{\"day\":\"$d\",\"lang\":\"both\",\"one_liner_max\":$MAX_PAPERS}")
  echo "one_liner_scoped -> $jid1"

  jid2=$(enqueue content_analysis_scoped "{\"day\":\"$d\",\"lang\":\"both\",\"content_analysis_max\":$MAX_PAPERS,\"content_analysis_concurrency\":$EXPLAIN_CONCURRENCY}")
  echo "content_analysis_scoped -> $jid2"

  jid3=$(enqueue image_caption_scoped "{\"day\":\"$d\",\"lang\":\"both\",\"image_caption_max\":$CAPTION_MAX,\"image_caption_per_paper\":$CAPTION_PER_PAPER,\"image_caption_concurrency\":$CAPTION_CONCURRENCY}")
  echo "image_caption_scoped -> $jid3"

  # Generate display provider (usually GLM) for zh+en
  jid4=$(enqueue paper_images_scoped "{\"day\":\"$d\",\"lang\":\"both\",\"paper_images_max_papers\":$MAX_PAPERS,\"paper_images_per_paper\":$PER_PAPER_IMAGES,\"paper_images_concurrency\":$IMAGES_CONCURRENCY}")
  echo "paper_images_scoped (display provider) -> $jid4"

  # Fill missing seedream images (zh+en)
  jid5=$(enqueue paper_images_scoped "{\"day\":\"$d\",\"lang\":\"both\",\"paper_images_max_papers\":$MAX_PAPERS,\"paper_images_per_paper\":$PER_PAPER_IMAGES,\"paper_images_concurrency\":$IMAGES_CONCURRENCY,\"paper_images_generate_only_display\":0,\"paper_images_providers\":[\"seedream\"]}")
  echo "paper_images_scoped (seedream fill) -> $jid5"

done

# Kick worker once at the end
curl -sS -H "x-admin-token: $TOKEN" -X POST "$BASE/api/admin/jobs/worker/kick" >/dev/null || true

echo

echo "OK: enqueued. Worker kicked."
echo "Check /admin Jobs panel or tail logs under: $PAPERTOK_LOG_DIR"
