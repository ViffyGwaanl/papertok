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

# Generate missing images for the latest HF Top10 by default (Phase 2: paper_images table)
# (does not run mineru/analysis/caption here; only images)
export PYTHONUNBUFFERED=1
export HF_TOP_N=${HF_TOP_N:-10}
export DOWNLOAD_PDF=0
export RUN_MINERU=0
export RUN_CONTENT_ANALYSIS=0
export RUN_IMAGE_CAPTION=0
export SKIP_LLM=1

export RUN_PAPER_IMAGES=1
export PAPER_IMAGES_PER_PAPER=${PAPER_IMAGES_PER_PAPER:-3}
export PAPER_IMAGES_MAX_PAPERS=${PAPER_IMAGES_MAX_PAPERS:-10}
export PAPER_GEN_IMAGE_SIZE=${PAPER_GEN_IMAGE_SIZE:-1440x2560}
# Use template planning by default (avoid blocking on text LLM)
# Use LLM to rewrite template prompts based on content_explain_cn.
export PAPER_IMAGES_PLAN_LLM=${PAPER_IMAGES_PLAN_LLM:-1}

exec .venv/bin/python -m scripts.daily_run
