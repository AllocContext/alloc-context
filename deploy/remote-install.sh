#!/usr/bin/env bash
# Run on the host after code is synced to ALLOC_CONTEXT_REMOTE.
# Invoked by deploy/rsync-to-vps.sh and GitHub Actions deploy job.
set -euo pipefail

REMOTE="${ALLOC_CONTEXT_REMOTE:-/opt/alloc-context}"
CONFIG="${REMOTE}/config/config.yaml"
PY="${REMOTE}/.venv/bin/python"
PIP="${REMOTE}/.venv/bin/pip"

install -d -m 750 -o trading -g trading "${REMOTE}/state"
install -d -m 750 -o trading -g trading "${REMOTE}/config"

if [[ ! -f "${CONFIG}" ]]; then
  install -m 640 "${REMOTE}/config/config.example.yaml" "${CONFIG}"
  chown trading:trading "${CONFIG}"
fi

if [[ ! -x "${PY}" ]]; then
  python3 -m venv "${REMOTE}/.venv"
fi

chown -R trading:trading "${REMOTE}/.venv" "${REMOTE}/config" "${REMOTE}/state"
"${PIP}" install -e "${REMOTE}[hosted]" -q
chown -R trading:trading "${REMOTE}"

TRADING_ROOT="$(dirname "${REMOTE}")"
if [[ -n "${ALLOC_CONTEXT_ENV_FILE:-}" ]]; then
  ENV_FILE="${ALLOC_CONTEXT_ENV_FILE}"
elif [[ -f "${TRADING_ROOT}/shared/.env" ]]; then
  ENV_FILE="${TRADING_ROOT}/shared/.env"
else
  ENV_FILE="${REMOTE}/.env"
fi

install_systemd_unit() {
  local unit="$1"
  local src="${REMOTE}/deploy/systemd/${unit}"
  local dest="/etc/systemd/system/${unit}"
  if [[ "${unit}" == *.service ]]; then
    sed \
      -e "s|/opt/alloc-context|${REMOTE}|g" \
      -e "s|EnvironmentFile=-.*|EnvironmentFile=-${ENV_FILE}|g" \
      -e "s|EnvironmentFile=/.*|EnvironmentFile=-${ENV_FILE}|g" \
      "${src}" > "${dest}"
  else
    cp "${src}" "${dest}"
  fi
}

for unit in \
  alloc-context-ingest.service \
  alloc-context-ingest.timer \
  alloc-context-mcp-http.service \
  alloc-context-backup.service \
  alloc-context-backup.timer; do
  install_systemd_unit "${unit}"
done

TRADING_ROOT="$(dirname "${REMOTE}")"
install -d -m 750 -o trading -g trading "${TRADING_ROOT}/backups"

# Disable legacy brief/alert timers if present from older installs.
CORE_BRIEF_TIMERS=(
  alloc-context-daily-brief.timer
  alloc-context-weekly-brief.timer
  alloc-context-alerts.timer
)
for unit in "${CORE_BRIEF_TIMERS[@]}"; do
  systemctl disable --now "${unit}" 2>/dev/null || true
done

systemctl daemon-reload

_enable_timer() {
  local unit="$1"
  if systemctl is-active --quiet "${unit}" 2>/dev/null; then
    systemctl enable "${unit}"
  else
    systemctl enable --now "${unit}"
  fi
}

_enable_timer alloc-context-ingest.timer
_enable_timer alloc-context-backup.timer

systemctl enable alloc-context-mcp-http.service
systemctl restart alloc-context-mcp-http.service

# Optional loopback MCP unit (no x402) — restart when present on the host.
if systemctl cat alloc-context-mcp-internal.service &>/dev/null; then
  systemctl restart alloc-context-mcp-internal.service
fi

bash "${REMOTE}/deploy/wait-for-mcp-ready.sh"

if [[ -n "${DEPLOYED_SHA:-}" ]]; then
  printf '%s\n' "${DEPLOYED_SHA}" > "${REMOTE}/.deployed-sha"
fi

echo "remote install ok: ${REMOTE}"
echo "alloc-context ingest timer enabled; MCP services restarted"
