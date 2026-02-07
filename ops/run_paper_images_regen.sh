#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
GEN_DIR="$ROOT_DIR/data/gen_images"

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

# 1) wipe existing generated images metadata + files ONCE.
# This job has KeepAlive-on-crash; we must avoid wiping again on restart.
MARKER="$ROOT_DIR/data/logs/.paper_images_regen_wiped"
mkdir -p "$ROOT_DIR/data/logs"

if [ ! -f "$MARKER" ]; then
  .venv/bin/python - <<'PY'
from sqlalchemy import text
from app.db.engine import engine

with engine.connect() as conn:
    conn.execute(text("DELETE FROM paper_images WHERE kind='generated'"))
    conn.commit()
print('OK: deleted paper_images(kind=generated)')
PY

  rm -rf "$GEN_DIR" || true
  mkdir -p "$GEN_DIR"
  date > "$MARKER"
else
  echo "INFO: regen wipe already done (marker exists): $MARKER"
  mkdir -p "$GEN_DIR"
fi

# 2) generate 5 images per paper
export PYTHONUNBUFFERED=1
export HF_TOP_N=0
export DOWNLOAD_PDF=0
export RUN_MINERU=0
export RUN_IMAGE_CAPTION=0
export RUN_CONTENT_ANALYSIS=0
export SKIP_LLM=1

export RUN_PAPER_IMAGES=1
export PAPER_IMAGES_PER_PAPER=${PAPER_IMAGES_PER_PAPER:-3}
export PAPER_IMAGES_MAX_PAPERS=${PAPER_IMAGES_MAX_PAPERS:-10}
export PAPER_GEN_IMAGE_SIZE=${PAPER_GEN_IMAGE_SIZE:-1440x2560}
# Use LLM to rewrite template prompts based on content_explain_cn.
export PAPER_IMAGES_PLAN_LLM=${PAPER_IMAGES_PLAN_LLM:-1}

exec .venv/bin/python -m scripts.daily_run
