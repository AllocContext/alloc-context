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
export ALLOC_CONTEXT_DB="${REPO_ROOT}/state/alloccontext.db"
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

_stop

if [[ "${SKIP_LOCAL_INGEST:-}" != "1" ]]; then
  echo "Running ingest (${CONFIG})..."
  if ! "${PY}" -m alloccontext --config "${CONFIG}" ingest; then
    echo "warning: ingest failed; continuing with existing database" >&2
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

cat <<EOF
Local stack ready.

  Health: http://${HOST}:${PORT}/health
  MCP:    http://${HOST}:${PORT}/mcp
  Config: ${CONFIG}
  Log:    ${LOGFILE}

  Stop:   scripts/local-down.sh
  Ingest: SKIP_LOCAL_INGEST=1 ./scripts/local-up.sh  # MCP only
EOF
