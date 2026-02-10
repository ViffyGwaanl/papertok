#!/usr/bin/env bash
set -euo pipefail

# Build a versioned release snapshot under DEPLOY_ROOT/releases/<release-id>.
#
# This script is designed to be safe for a running system because it builds in an
# isolated directory. The only potential impact is CPU/IO usage during npm build.

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_ROOT="${PAPERTOK_DEPLOY_ROOT:-$HOME/papertok-deploy}"

# Release id: timestamp + git sha (best effort)
SHA="nogit"
if command -v git >/dev/null 2>&1 && git -C "$SRC_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  SHA="$(git -C "$SRC_ROOT" rev-parse --short HEAD)"
fi
REL_ID="$(date +%Y%m%d-%H%M%S)-$SHA"
REL_DIR="$DEPLOY_ROOT/releases/$REL_ID"

mkdir -p "$DEPLOY_ROOT/releases"
mkdir -p "$REL_DIR"

# Copy source tree into release (exclude runtime state)
rsync -a --delete \
  --exclude '.env' \
  --exclude 'data/' \
  --exclude 'backend/.venv/' \
  --exclude 'frontend/wikitok/frontend/node_modules/' \
  --exclude 'frontend/wikitok/frontend/dist/' \
  "$SRC_ROOT/" "$REL_DIR/"

# Wire shared state
ln -sfn "$DEPLOY_ROOT/shared/.env" "$REL_DIR/.env"
ln -sfn "$DEPLOY_ROOT/shared/data" "$REL_DIR/data"

# Reuse shared venv if available
if [[ -e "$DEPLOY_ROOT/shared/venv" ]]; then
  ln -sfn "$DEPLOY_ROOT/shared/venv" "$REL_DIR/backend/.venv"
fi

# Build frontend dist inside release
FRONT="$REL_DIR/frontend/wikitok/frontend"
if [[ -f "$FRONT/package.json" ]]; then
  (cd "$FRONT" && npm ci && npm run build)
else
  echo "WARN: frontend not found at $FRONT; skipping build"
fi

# Metadata
cat >"$REL_DIR/RELEASE.json" <<EOF
{"id":"$REL_ID","sha":"$SHA","built_at":"$(date -Iseconds)"}
EOF

echo "OK: built release $REL_ID"
echo "Path: $REL_DIR"
