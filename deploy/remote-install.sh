#!/usr/bin/env bash
# Run on the host after code is synced to ALLOC_CONTEXT_REMOTE.
# Invoked by deploy/rsync-to-vps.sh and GitHub Actions deploy job.
set -euo pipefail

REMOTE="${ALLOC_CONTEXT_REMOTE:-/opt/alloc-context}"
CONFIG="${REMOTE}/config/config.yaml"
PY="${REMOTE}/.venv/bin/python"
PIP="${REMOTE}/.venv/bin/pip"

install -d -m 750 -o trading -g trading "${REMOTE}/state/briefs/daily"
install -d -m 750 -o trading -g trading "${REMOTE}/state/briefs/weekly"
install -d -m 750 -o trading -g trading "${REMOTE}/config"

# One-time state migration from market-analyst checkout (pre-AllocContext).
OLD_REMOTE="/opt/trading/market-analyst"
if [[ -d "${OLD_REMOTE}/state" && ! -e "${REMOTE}/state/alloccontext.db" ]]; then
  if [[ -f "${OLD_REMOTE}/state/analyst.db" ]]; then
    cp -a "${OLD_REMOTE}/state/." "${REMOTE}/state/"
    chown -R trading:trading "${REMOTE}/state"
    echo "migrated state from ${OLD_REMOTE}/state"
  fi
fi

if [[ ! -f "${CONFIG}" ]]; then
  install -m 640 "${REMOTE}/config/config.example.yaml" "${CONFIG}"
  chown trading:trading "${CONFIG}"
fi

if [[ ! -x "${PY}" ]]; then
  python3 -m venv "${REMOTE}/.venv"
fi

chown -R trading:trading "${REMOTE}/.venv" "${REMOTE}/config" "${REMOTE}/state"
"${PIP}" install -e "${REMOTE}" -q
chown -R trading:trading "${REMOTE}"

"${PY}" "${REMOTE}/deploy/render-systemd-timers.py" \
  --config "${CONFIG}" \
  --repo-root "${REMOTE}"

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
  alloc-context-ingest.timer \
  alloc-context-daily-brief.service \
  alloc-context-daily-brief.timer \
  alloc-context-weekly-brief.service \
  alloc-context-weekly-brief.timer; do
  install_systemd_unit "${unit}"
done

# Disable pre-rename systemd units if present from prior installs.
STALE_UNITS=(
  market-analyst-ingest.timer
  market-analyst-daily-brief.timer
  market-analyst-weekly-brief.timer
)
for unit in "${STALE_UNITS[@]}"; do
  systemctl disable --now "${unit}" 2>/dev/null || true
done

systemctl daemon-reload

# Avoid re-starting active timers on deploy — Persistent ingest catch-up is
# fine, but brief timers would email immediately after today's schedule.
_enable_timer() {
  local unit="$1"
  if systemctl is-active --quiet "${unit}" 2>/dev/null; then
    systemctl enable "${unit}"
  else
    systemctl enable --now "${unit}"
  fi
}

_enable_timer alloc-context-ingest.timer
_enable_timer alloc-context-daily-brief.timer
_enable_timer alloc-context-weekly-brief.timer

if [[ -n "${DEPLOYED_SHA:-}" ]]; then
  printf '%s\n' "${DEPLOYED_SHA}" > "${REMOTE}/.deployed-sha"
fi

echo "remote install ok: ${REMOTE}"
echo "alloc-context timers enabled"
