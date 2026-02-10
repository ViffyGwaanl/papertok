#!/usr/bin/env bash
set -euo pipefail

# Prepare shared resources for release-based deployment.
# Safe to run while the service is running (no restart).

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_ROOT="${PAPERTOK_DEPLOY_ROOT:-$HOME/papertok-deploy}"

mkdir -p "$DEPLOY_ROOT/shared" "$DEPLOY_ROOT/releases"

# By default, reuse the current repo's .env and data/ as shared sources.
# This avoids moving any existing state during the first migration.
# You can later replace these symlinks with real copies.
if [[ ! -e "$DEPLOY_ROOT/shared/.env" ]]; then
  if [[ -f "$SRC_ROOT/.env" ]]; then
    ln -s "$SRC_ROOT/.env" "$DEPLOY_ROOT/shared/.env"
    echo "OK: linked shared/.env -> $SRC_ROOT/.env"
  else
    echo "WARN: $SRC_ROOT/.env not found; create $DEPLOY_ROOT/shared/.env manually"
  fi
fi

if [[ ! -e "$DEPLOY_ROOT/shared/data" ]]; then
  if [[ -d "$SRC_ROOT/data" ]]; then
    ln -s "$SRC_ROOT/data" "$DEPLOY_ROOT/shared/data"
    echo "OK: linked shared/data -> $SRC_ROOT/data"
  else
    mkdir -p "$DEPLOY_ROOT/shared/data"
    echo "OK: created empty shared/data"
  fi
fi

# Optional: provide a shared venv path. We do NOT create a new venv here by default.
# Later you can promote to a fully isolated venv under $DEPLOY_ROOT/shared/venv.
if [[ ! -e "$DEPLOY_ROOT/shared/venv" ]]; then
  if [[ -d "$SRC_ROOT/backend/.venv" ]]; then
    ln -s "$SRC_ROOT/backend/.venv" "$DEPLOY_ROOT/shared/venv"
    echo "OK: linked shared/venv -> $SRC_ROOT/backend/.venv (reusing existing venv)"
  else
    echo "INFO: no backend/.venv found; you can create one at $DEPLOY_ROOT/shared/venv"
  fi
fi

echo "DONE: DEPLOY_ROOT=$DEPLOY_ROOT"
