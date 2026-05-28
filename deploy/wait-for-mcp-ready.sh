#!/usr/bin/env bash
# Wait for public and internal MCP listeners before post-deploy smoke.
set -euo pipefail

PUBLIC_HEALTH="${MCP_PUBLIC_HEALTH_URL:-http://127.0.0.1:8000/health}"
INTERNAL_MCP="${MCP_INTERNAL_MCP_URL:-http://127.0.0.1:8001/mcp}"
TIMEOUT="${MCP_READY_TIMEOUT_SECONDS:-90}"
INTERVAL="${MCP_READY_INTERVAL_SECONDS:-2}"

deadline=$(( $(date +%s) + TIMEOUT ))

wait_public() {
  while (( $(date +%s) < deadline )); do
    if curl -sf -o /dev/null "${PUBLIC_HEALTH}"; then
      echo "MCP ready: ${PUBLIC_HEALTH}"
      return 0
    fi
    sleep "${INTERVAL}"
  done
  echo "timeout waiting for ${PUBLIC_HEALTH}" >&2
  return 1
}

wait_internal() {
  while (( $(date +%s) < deadline )); do
    if curl -sf -o /dev/null \
      -H "Accept: application/json" \
      -H "Content-Type: application/json" \
      -X POST "${INTERNAL_MCP}" \
      -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'; then
      echo "MCP ready: ${INTERNAL_MCP}"
      return 0
    fi
    sleep "${INTERVAL}"
  done
  echo "timeout waiting for ${INTERNAL_MCP}" >&2
  return 1
}

wait_public
wait_internal
