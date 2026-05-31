#!/usr/bin/env bash
# Publish server.json to the official MCP Registry (OIDC in CI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLISHER="${1:-${ROOT}/mcp-publisher}"
SERVER_JSON="${SERVER_JSON:-${ROOT}/server.json}"

if [[ ! -x "${PUBLISHER}" ]]; then
  bash "${ROOT}/scripts/install-mcp-publisher.sh" "${PUBLISHER}"
fi

bash "${ROOT}/scripts/wait-for-pypi.sh"

"${PUBLISHER}" login github-oidc

set +e
OUTPUT=$("${PUBLISHER}" publish --file "${SERVER_JSON}" 2>&1)
STATUS=$?
set -e

echo "${OUTPUT}"

if [[ ${STATUS} -eq 0 ]]; then
  exit 0
fi

if echo "${OUTPUT}" | grep -q "cannot publish duplicate version"; then
  echo "Registry already has this version; treating as success"
  exit 0
fi

exit "${STATUS}"
