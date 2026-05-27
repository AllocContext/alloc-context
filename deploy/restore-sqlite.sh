#!/usr/bin/env bash
# Restore SQLite state from a backup directory (stop MCP/ingest first).
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-dir>  # e.g. /opt/trading/backups/20260527T041500Z" >&2
  exit 1
fi

REMOTE="${ALLOC_CONTEXT_REMOTE:-/opt/trading/alloc-context}"
TRADING_ROOT="${TRADING_ROOT:-$(dirname "${REMOTE}")}"
PY="${REMOTE}/.venv/bin/python"
SCRIPT="${REMOTE}/deploy/backup_sqlite.py"
BACKUP_DIR="$1"

UNITS=(
  alloc-context-ingest.timer
  alloc-context-mcp-http.service
  alloc-context-mcp-internal.service
  alloc-context-operator-healthcheck.timer
  alloc-context-operator-alerts.timer
  alloc-context-operator-daily-brief.timer
  alloc-context-operator-weekly-brief.timer
  alloc-context-operator-monthly-review.timer
)

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Stopping timers and MCP services..."
  for unit in "${UNITS[@]}"; do
    systemctl stop "${unit}" 2>/dev/null || true
  done
fi

"${PY}" "${SCRIPT}" restore --trading-root "${TRADING_ROOT}" "${BACKUP_DIR}"

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Restarting MCP services..."
  systemctl start alloc-context-mcp-http.service alloc-context-mcp-internal.service
  for unit in "${UNITS[@]}"; do
    systemctl start "${unit}" 2>/dev/null || true
  done
fi

echo "restore complete"
