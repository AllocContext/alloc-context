#!/usr/bin/env bash
# Poll PyPI until a release version is indexed (MCP Registry validates PyPI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE="${PYPI_PACKAGE:-alloc-context}"
VERSION="${PYPI_VERSION:-$(python3 "${ROOT}/scripts/bump_version.py" --current)}"
URL="https://pypi.org/pypi/${PACKAGE}/${VERSION}/json"
TIMEOUT="${PYPI_WAIT_TIMEOUT_SECONDS:-300}"
INTERVAL="${PYPI_WAIT_INTERVAL_SECONDS:-10}"

deadline=$(( $(date +%s) + TIMEOUT ))

echo "Waiting for PyPI ${PACKAGE}==${VERSION} at ${URL}"

while (( $(date +%s) < deadline )); do
  if curl -fsS -o /dev/null "${URL}"; then
    echo "PyPI index ready: ${PACKAGE}==${VERSION}"
    exit 0
  fi
  sleep "${INTERVAL}"
done

echo "timeout waiting for ${PACKAGE}==${VERSION} on PyPI" >&2
exit 1
