#!/usr/bin/env bash
# Start local internal MCP (no x402) with a dev ingest cache.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CONFIG="${ALLOC_CONTEXT_CONFIG:-${REPO_ROOT}/config/config.dev.yaml}"
PORT="${DEV_MCP_PORT:-8001}"
HOST="${DEV_MCP_HOST:-127.0.0.1}"
PIDFILE="${REPO_ROOT}/state/dev-mcp.pid"
LOGFILE="${REPO_ROOT}/state/dev-mcp.log"
DEV_DB="${REPO_ROOT}/state/dev/alloccontext.db"

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is required for dev-up health checks" >&2
  exit 1
fi

_pick_python() {
  for candidate in python3.11 python3.12 python3; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      echo "${candidate}"
      return 0
    fi
  done
  echo "error: python3.11+ is required" >&2
  exit 1
}

PY="${REPO_ROOT}/.venv/bin/python"
PIP="${REPO_ROOT}/.venv/bin/pip"

if [[ ! -x "${PY}" ]]; then
  "$(_pick_python)" -m venv "${REPO_ROOT}/.venv"
fi
"${PIP}" install -q -e ".[dev]"

install -d -m 755 "${REPO_ROOT}/state/dev" "${REPO_ROOT}/config"
if [[ ! -f "${CONFIG}" ]]; then
  echo "error: missing ${CONFIG}" >&2
  exit 1
fi

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

# Dev stack must not inherit a production ALLOC_CONTEXT_CONFIG from .env.
export ALLOC_CONTEXT_CONFIG="${CONFIG}"

_stop_dev_mcp() {
  if [[ ! -f "${PIDFILE}" ]]; then
    return 0
  fi
  pid="$(cat "${PIDFILE}")"
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    wait "${pid}" 2>/dev/null || true
  fi
  rm -f "${PIDFILE}"
}

_port_listener_pid() {
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi
  lsof -ti "tcp:${PORT}" -sTCP:LISTEN 2>/dev/null | head -n 1
}

_assert_port_available() {
  local listener
  listener="$(_port_listener_pid)"
  if [[ -z "${listener}" ]]; then
    return 0
  fi
  if [[ -f "${PIDFILE}" ]] && [[ "$(cat "${PIDFILE}")" == "${listener}" ]]; then
    return 0
  fi
  echo "error: port ${PORT} already in use (pid ${listener})" >&2
  echo "       stop the other service or set DEV_MCP_PORT" >&2
  exit 1
}

_stop_dev_mcp
_assert_port_available

if [[ "${SKIP_DEV_INGEST:-}" != "1" ]]; then
  echo "Running ingest (${CONFIG})..."
  if ! "${PY}" -m alloccontext --config "${CONFIG}" ingest; then
    if [[ -f "${DEV_DB}" ]]; then
      echo "warning: ingest failed; continuing with existing ${DEV_DB}" >&2
    else
      echo "error: ingest failed and no dev database exists at ${DEV_DB}" >&2
      exit 1
    fi
  fi
fi

echo "Starting internal MCP on http://${HOST}:${PORT}/mcp (no x402)..."
nohup "${PY}" -m alloccontext --config "${CONFIG}" mcp \
  --transport http --host "${HOST}" --port "${PORT}" \
  >> "${LOGFILE}" 2>&1 &
echo "$!" > "${PIDFILE}"

ready=0
for _ in $(seq 1 30); do
  if curl -sf "http://${HOST}:${PORT}/health" >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "${ready}" -ne 1 ]]; then
  echo "error: MCP did not become healthy; see ${LOGFILE}" >&2
  _stop_dev_mcp
  exit 1
fi

if ! kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
  echo "error: MCP exited during startup; see ${LOGFILE}" >&2
  rm -f "${PIDFILE}"
  exit 1
fi

cat <<EOF
Dev stack ready.

  Health: http://${HOST}:${PORT}/health
  MCP:    http://${HOST}:${PORT}/mcp
  Config: ${CONFIG}
  Log:    ${LOGFILE}

  Stop:   scripts/dev-down.sh
  Status: python -m alloccontext status --mcp-url http://${HOST}:${PORT}/health

Optional operator (second checkout):
  Set mcp.url to http://${HOST}:${PORT}/mcp in operator config.yaml
EOF
