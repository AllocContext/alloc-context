#!/usr/bin/env bash
# Local self-host stack: loopback HTTP MCP on :8001 (no x402).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CONFIG="${ALLOC_CONTEXT_CONFIG:-${REPO_ROOT}/config/config.yaml}"
PORT="${LOCAL_MCP_PORT:-8001}"
HOST="${LOCAL_MCP_HOST:-127.0.0.1}"
PIDFILE="${REPO_ROOT}/state/local-mcp.pid"
LOGFILE="${REPO_ROOT}/state/local-mcp.log"
LOCAL_DB="${ALLOC_CONTEXT_DB:-${REPO_ROOT}/state/alloccontext.db}"

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is required" >&2
  exit 1
fi

PY="${REPO_ROOT}/.venv/bin/python"
PIP="${REPO_ROOT}/.venv/bin/pip"

if [[ ! -x "${PY}" ]]; then
  python3 -m venv "${REPO_ROOT}/.venv"
fi
"${PIP}" install -q -e ".[dev,mcp]"

install -d -m 755 "${REPO_ROOT}/state" "${REPO_ROOT}/config"
if [[ ! -f "${CONFIG}" ]]; then
  echo "error: missing ${CONFIG}" >&2
  echo "  cp config/config.example.yaml config/config.yaml" >&2
  exit 1
fi

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

export ALLOC_CONTEXT_CONFIG="${CONFIG}"
export ALLOC_CONTEXT_DB="${LOCAL_DB}"
export ALLOC_CONTEXT_ALLOW_UNPAID_HTTP=1

_stop() {
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
  echo "       stop the other service or set LOCAL_MCP_PORT" >&2
  exit 1
}

_stop
_assert_port_available

if [[ "${SKIP_LOCAL_INGEST:-}" != "1" ]]; then
  echo "Running ingest (${CONFIG})..."
  if ! "${PY}" -m alloccontext --config "${CONFIG}" ingest; then
    if [[ -f "${LOCAL_DB}" ]]; then
      echo "warning: ingest failed; continuing with existing ${LOCAL_DB}" >&2
    else
      echo "error: ingest failed and no database exists at ${LOCAL_DB}" >&2
      exit 1
    fi
  fi
fi

echo "Starting local MCP on http://${HOST}:${PORT}/mcp ..."
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
  _stop
  exit 1
fi

if ! kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
  echo "error: MCP exited during startup; see ${LOGFILE}" >&2
  rm -f "${PIDFILE}"
  exit 1
fi

cat <<EOF
Local stack ready.

  Health: http://${HOST}:${PORT}/health
  MCP:    http://${HOST}:${PORT}/mcp
  Config: ${CONFIG}
  Log:    ${LOGFILE}

  Stop:   scripts/local-down.sh
  Ingest: SKIP_LOCAL_INGEST=1 ./scripts/local-up.sh  # MCP only
EOF
