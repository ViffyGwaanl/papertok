#!/usr/bin/env bash
set -euo pipefail

# Deprecated wrapper kept for backward compatibility.
# Use: ops/run_daily.sh (Mode C heavy pipeline)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/run_daily.sh"
