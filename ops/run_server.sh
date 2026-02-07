#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

cd "$BACKEND_DIR"

# Load env (kept out of git)
set -a
if [ -f "$ROOT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
else
  echo "ERROR: $ROOT_DIR/.env not found (single source of truth)." >&2
  exit 1
fi
set +a

# Run API + (optional) built frontend
# Default: listen on LAN (0.0.0.0) so phones on the same Wi‑Fi can access.
PAPERTOK_HOST=${PAPERTOK_HOST:-0.0.0.0}
PAPERTOK_PORT=${PAPERTOK_PORT:-8000}

exec .venv/bin/python -m uvicorn app.main:app --host "$PAPERTOK_HOST" --port "$PAPERTOK_PORT"
