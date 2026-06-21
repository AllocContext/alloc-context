#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDFILE="${REPO_ROOT}/state/local-mcp.pid"
if [[ -f "${PIDFILE}" ]]; then
  pid="$(cat "${PIDFILE}")"
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    wait "${pid}" 2>/dev/null || true
  fi
  rm -f "${PIDFILE}"
  echo "Stopped local MCP (pid ${pid})."
else
  echo "No local MCP pidfile."
fi
