#!/usr/bin/env bash
set -euo pipefail

# Dev-only helper: run full pipeline on the EXISTING dataset.
# Key property: does NOT fetch new HF daily papers (HF_TOP_N=0).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

cd "$BACKEND_DIR"

# Load env
set -a
if [ -f "$ROOT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
else
  echo "ERROR: $ROOT_DIR/.env not found" >&2
  exit 1
fi
set +a

export PYTHONUNBUFFERED=1

# Freeze dataset: no new ingestion.
export HF_TOP_N=0
# Use cached PDFs only.
export DOWNLOAD_PDF=0

# Run full pipeline (pending-only):
export RUN_MINERU=1
export RUN_CONTENT_ANALYSIS=1
export RUN_IMAGE_CAPTION=1
export RUN_PAPER_IMAGES=1

# Skip one-liner generation at the end (optional)
export SKIP_LLM=1

exec .venv/bin/python -m scripts.daily_run
