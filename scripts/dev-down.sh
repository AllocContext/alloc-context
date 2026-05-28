#!/usr/bin/env bash
# Stop the local dev MCP started by scripts/dev-up.sh.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDFILE="${REPO_ROOT}/state/dev-mcp.pid"

if [[ ! -f "${PIDFILE}" ]]; then
  echo "Dev MCP is not running (no ${PIDFILE})."
  exit 0
fi

pid="$(cat "${PIDFILE}")"
if kill -0 "${pid}" 2>/dev/null; then
  kill "${pid}" 2>/dev/null || true
  wait "${pid}" 2>/dev/null || true
  echo "Stopped dev MCP (pid ${pid})."
else
  echo "Removed stale pid file (pid ${pid} not running)."
fi
rm -f "${PIDFILE}"
