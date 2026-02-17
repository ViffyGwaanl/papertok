#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

cd "$BACKEND_DIR"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "ERROR: papertok/.env not found. Copy from .env.example and fill keys." >&2
  exit 1
fi

mkdir -p "$ROOT_DIR/data/logs"

# load .env into environment for the job
set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

# Mode C (heavy): only process today's HF top10, end-to-end.
export HF_TOP_N=${HF_TOP_N:-10}

export DOWNLOAD_PDF=${DOWNLOAD_PDF:-1}

export RUN_MINERU=${RUN_MINERU:-1}
export MINERU_MAX=${MINERU_MAX:-10}

export RUN_CONTENT_ANALYSIS=${RUN_CONTENT_ANALYSIS:-1}
export CONTENT_ANALYSIS_MAX=${CONTENT_ANALYSIS_MAX:-10}

export RUN_IMAGE_CAPTION=${RUN_IMAGE_CAPTION:-1}
export IMAGE_CAPTION_MAX=${IMAGE_CAPTION_MAX:-100000}
export IMAGE_CAPTION_PER_PAPER=${IMAGE_CAPTION_PER_PAPER:-100000}
export IMAGE_CAPTION_CONTEXT_CHARS=${IMAGE_CAPTION_CONTEXT_CHARS:-2000}
export IMAGE_CAPTION_CONTEXT_STRATEGY=${IMAGE_CAPTION_CONTEXT_STRATEGY:-merge}
export IMAGE_CAPTION_CONTEXT_OCCURRENCES=${IMAGE_CAPTION_CONTEXT_OCCURRENCES:-3}

export RUN_PAPER_IMAGES=${RUN_PAPER_IMAGES:-1}
export PAPER_IMAGES_MAX_PAPERS=${PAPER_IMAGES_MAX_PAPERS:-10}
export PAPER_IMAGES_PER_PAPER=${PAPER_IMAGES_PER_PAPER:-3}
# Generate BOTH providers by default (keep two sets of images)
export PAPER_IMAGES_PROVIDERS=${PAPER_IMAGES_PROVIDERS:-seedream,glm}
# Which provider the FEED should prefer: seedream|glm|auto
export PAPER_IMAGES_DISPLAY_PROVIDER=${PAPER_IMAGES_DISPLAY_PROVIDER:-seedream}

export PAPER_IMAGES_PLAN_LLM=${PAPER_IMAGES_PLAN_LLM:-1}
export PAPER_IMAGES_PLAN_EXPLAIN_CHARS=${PAPER_IMAGES_PLAN_EXPLAIN_CHARS:-20000}
export PAPER_GEN_IMAGE_SIZE=${PAPER_GEN_IMAGE_SIZE:-1440x2560}
# GLM-Image size (<=2048)
export PAPER_GLM_IMAGE_SIZE=${PAPER_GLM_IMAGE_SIZE:-1088x1920}

# EPUB generation (pandoc)
export RUN_EPUB=${RUN_EPUB:-1}
export EPUB_MAX=${EPUB_MAX:-10}

# ensure venv
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python -m scripts.daily_run
fi

# fallback
exec python3 -m scripts.daily_run
