#!/usr/bin/env bash
# Break-glass: sync this repo to a remote host and reinstall the package.
#
# Normal releases use the GitHub Actions **release** workflow (see
# docs/publishing.md). Operator repo still deploys on main push.
# Requires environment variables — no host or key defaults are baked in.
#
# Usage:
#   VPS_HOST=203.0.113.10 SSH_KEY=~/.ssh/deploy_key ./deploy/rsync-to-vps.sh
#
# Optional:
#   VPS_USER=root
#   ALLOC_CONTEXT_REMOTE=/opt/alloc-context
#   DEPLOY_FORCE=1   # skip origin/main confirmation prompt
set -euo pipefail

VPS_HOST="${VPS_HOST:-${VPS_IP:-}}"
SSH_KEY="${SSH_KEY:-}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${ALLOC_CONTEXT_REMOTE:-/opt/alloc-context}"

if [[ -z "${VPS_HOST}" ]]; then
  echo "error: set VPS_HOST (or VPS_IP) to the deploy target" >&2
  exit 1
fi
if [[ -z "${SSH_KEY}" || ! -f "${SSH_KEY}" ]]; then
  echo "error: set SSH_KEY to a readable private key path" >&2
  exit 1
fi

if ! git -C "${REPO_ROOT}" merge-base --is-ancestor origin/main HEAD 2>/dev/null; then
  echo "error: HEAD is not based on origin/main — fetch/rebase main first" >&2
  exit 1
fi

LOCAL_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
REMOTE_SHA="$(git -C "${REPO_ROOT}" rev-parse origin/main)"
if [[ "${LOCAL_SHA}" != "${REMOTE_SHA}" ]]; then
  echo "warning: HEAD (${LOCAL_SHA:0:7}) != origin/main (${REMOTE_SHA:0:7})" >&2
  echo "         push to origin/main or check out origin/main before deploying" >&2
  if [[ "${DEPLOY_FORCE:-}" != "1" ]]; then
    read -r -p "Deploy anyway? [y/N] " confirm
    [[ "${confirm}" == [yY] ]] || exit 1
  fi
fi

USER="${VPS_USER:-root}"

echo "==> rsync alloc-context to ${USER}@${VPS_HOST}:${REMOTE}"
rsync -avz --delete \
  --exclude '.venv/' \
  --exclude '.git/' \
  --exclude '.pytest_cache/' \
  --exclude '.env' \
  --exclude '/state/' \
  --exclude 'config/config.yaml' \
  -e "ssh -i ${SSH_KEY} -o IdentitiesOnly=yes" \
  "${REPO_ROOT}/" "${USER}@${VPS_HOST}:${REMOTE}/"

echo "==> pip install -e, enable systemd, restart MCP"
ssh -i "${SSH_KEY}" -o IdentitiesOnly=yes "${USER}@${VPS_HOST}" \
  "DEPLOYED_SHA=${LOCAL_SHA} ALLOC_CONTEXT_REMOTE=${REMOTE} bash -s" \
  < "${REPO_ROOT}/deploy/remote-install.sh"

echo "==> done (state/, config/config.yaml, and .env on host unchanged; deployed ${LOCAL_SHA:0:7})"
