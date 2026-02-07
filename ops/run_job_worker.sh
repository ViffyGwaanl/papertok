#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

cd "$BACKEND_DIR"

set -a
if [ -f "$ROOT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
else
  echo "ERROR: $ROOT_DIR/.env not found (single source of truth)." >&2
  exit 1
fi
set +a

export PYTHONUNBUFFERED=1

# Process up to N jobs per run
MAX_JOBS=${JOB_WORKER_MAX_JOBS:-3}

exec .venv/bin/python -m scripts.job_worker "$MAX_JOBS"
