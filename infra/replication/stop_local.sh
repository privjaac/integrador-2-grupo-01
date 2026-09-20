#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="${REPLICATION_RUNTIME_DIR:-$SCRIPT_DIR/.runtime}"
PG_BINDIR="${PG_BINDIR:-$(pg_config --bindir)}"
export PATH="$PG_BINDIR:$PATH"

for node in replica primary; do
  if [[ -f "$RUNTIME_DIR/$node/postmaster.pid" ]]; then
    pg_ctl -D "$RUNTIME_DIR/$node" stop -m fast >/dev/null
  fi
done

if [[ "${1:-}" == "--clean" ]]; then
  rm -rf "$RUNTIME_DIR"
fi
