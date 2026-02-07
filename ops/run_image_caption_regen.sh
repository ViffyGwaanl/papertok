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

# 1) Clear all cached captions ONCE per regen run set (avoid repeated wipe on launchd restarts)
MARKER="$ROOT_DIR/data/.image_caption_regen_wipe_done"
if [ ! -f "$MARKER" ]; then
  .venv/bin/python - <<'PY'
from sqlalchemy import text
from app.db.engine import engine

with engine.connect() as conn:
    conn.execute(text("UPDATE papers SET image_captions_json=NULL WHERE raw_text_path IS NOT NULL"))
    conn.commit()
print('OK: cleared image_captions_json for papers with raw_text_path')
PY
  date -Iseconds > "$MARKER" || true
else
  echo "SKIP: wipe already done (marker exists: $MARKER)"
fi

# 2) Re-generate captions for ALL images, with markdown context
export PYTHONUNBUFFERED=1
export HF_TOP_N=0
export DOWNLOAD_PDF=0
export RUN_MINERU=0
export RUN_CONTENT_ANALYSIS=0
export RUN_PAPER_IMAGES=0
export SKIP_LLM=1

export RUN_IMAGE_CAPTION=1
export IMAGE_CAPTION_MAX=${IMAGE_CAPTION_MAX:-100000}
export IMAGE_CAPTION_PER_PAPER=${IMAGE_CAPTION_PER_PAPER:-100000}
export IMAGE_CAPTION_CONTEXT_CHARS=${IMAGE_CAPTION_CONTEXT_CHARS:-2000}
export IMAGE_CAPTION_CONTEXT_STRATEGY=${IMAGE_CAPTION_CONTEXT_STRATEGY:-merge}
export IMAGE_CAPTION_CONTEXT_OCCURRENCES=${IMAGE_CAPTION_CONTEXT_OCCURRENCES:-3}

exec .venv/bin/python -m scripts.daily_run
