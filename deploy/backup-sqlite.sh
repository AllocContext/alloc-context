#!/usr/bin/env bash
# Nightly SQLite backups for /opt/trading (core + operator state).
set -euo pipefail

REMOTE="${ALLOC_CONTEXT_REMOTE:-/opt/trading/alloc-context}"
TRADING_ROOT="${TRADING_ROOT:-$(dirname "${REMOTE}")}"
PY="${REMOTE}/.venv/bin/python"
SCRIPT="${REMOTE}/deploy/backup_sqlite.py"

if [[ ! -x "${PY}" ]]; then
  echo "FAIL: missing ${PY}" >&2
  exit 1
fi

exec "${PY}" "${SCRIPT}" backup --trading-root "${TRADING_ROOT}"
