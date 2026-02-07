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

# Rebuild content_explain_cn from MinerU markdown.
export PYTHONUNBUFFERED=1
export HF_TOP_N=0
export DOWNLOAD_PDF=0
export RUN_MINERU=0
export RUN_IMAGE_CAPTION=0
export RUN_PAPER_IMAGES=0
export SKIP_LLM=1

export RUN_CONTENT_ANALYSIS=1
export CONTENT_ANALYSIS_MAX=100000

exec .venv/bin/python -m scripts.daily_run
