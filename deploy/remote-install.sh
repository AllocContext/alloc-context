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

ENV_FILE="${ALLOC_CONTEXT_ENV_FILE:-${REMOTE}/.env}"

install_systemd_unit() {
  local unit="$1"
  local src="${REMOTE}/deploy/systemd/${unit}"
  local dest="/etc/systemd/system/${unit}"
  if [[ "${unit}" == *.service ]]; then
    sed \
      -e "s|/opt/alloc-context|${REMOTE}|g" \
      -e "s|EnvironmentFile=-.*|EnvironmentFile=${ENV_FILE}|g" \
      "${src}" > "${dest}"
  else
    cp "${src}" "${dest}"
  fi
}

for unit in \
  alloc-context-ingest.service \
  alloc-context-ingest.timer; do
  install_systemd_unit "${unit}"
done

# Disable core brief timers (briefs run from alloc-context-operator).
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

if [[ -n "${DEPLOYED_SHA:-}" ]]; then
  printf '%s\n' "${DEPLOYED_SHA}" > "${REMOTE}/.deployed-sha"
fi

echo "remote install ok: ${REMOTE}"
echo "alloc-context ingest timer enabled"
