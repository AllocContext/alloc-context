#!/usr/bin/env bash
# Run production smoke on the VPS via SSH (CI and local ops).
set -euo pipefail

VPS_HOST="${VPS_HOST:?VPS_HOST is required}"
VPS_USER="${VPS_USER:-root}"
SSH_KEY="${DEPLOY_SSH_KEY:-${HOME}/.ssh/deploy_key}"
OPERATOR_REMOTE="${ALLOC_CONTEXT_OPERATOR_REMOTE:-/opt/trading/alloc-context-operator}"
CORE_REMOTE="${ALLOC_CONTEXT_REMOTE:-/opt/trading/alloc-context}"

remote_env=(
  "ALLOC_CONTEXT_REMOTE=${CORE_REMOTE}"
  "ALLOC_CONTEXT_OPERATOR_REMOTE=${OPERATOR_REMOTE}"
)
if [[ -n "${SMOKE_EXPECT_OPERATOR_SHA:-}" ]]; then
  remote_env+=("SMOKE_EXPECT_OPERATOR_SHA=${SMOKE_EXPECT_OPERATOR_SHA}")
fi
if [[ -n "${SMOKE_EXPECT_CORE_SHA:-}" ]]; then
  remote_env+=("SMOKE_EXPECT_CORE_SHA=${SMOKE_EXPECT_CORE_SHA}")
fi

remote_cmd="cd \"${OPERATOR_REMOTE}\" && env ${remote_env[*]} \
.venv/bin/python -m alloccontext_operator --config config/config.yaml smoke"

ssh -i "${SSH_KEY}" -o IdentitiesOnly=yes \
  "${VPS_USER}@${VPS_HOST}" \
  "sudo -u trading bash -lc $(printf '%q' "${remote_cmd}")"
