#!/usr/bin/env bash
# Poll PyPI until a release version is indexed (MCP Registry validates PyPI).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE="${PYPI_PACKAGE:-alloc-context}"
VERSION="${PYPI_VERSION:-$(python3 "${ROOT}/scripts/bump_version.py" --current)}"
URL="https://pypi.org/pypi/${PACKAGE}/${VERSION}/json"
TIMEOUT="${PYPI_WAIT_TIMEOUT_SECONDS:-600}"
INTERVAL="${PYPI_WAIT_INTERVAL_SECONDS:-15}"
INITIAL="${PYPI_WAIT_INITIAL_SECONDS:-30}"
STABLE_POLLS="${PYPI_WAIT_STABLE_POLLS:-2}"
CHECKER="${ROOT}/scripts/check_pypi_release_json.py"

if (( INITIAL > 0 )); then
  echo "Initial PyPI wait ${INITIAL}s after upload (index propagation)"
  sleep "${INITIAL}"
fi

deadline=$(( $(date +%s) + TIMEOUT ))
stable=0

echo "Waiting for PyPI ${PACKAGE}==${VERSION} at ${URL}"
echo "Require ${STABLE_POLLS} consecutive ready polls (interval ${INTERVAL}s)"

while (( $(date +%s) < deadline )); do
  body=""
  if body=$(curl -fsS \
    -H "Cache-Control: no-cache" \
    -H "Accept: application/json" \
    "${URL}?_=${RANDOM}"); then
    if printf '%s' "${body}" | python3 "${CHECKER}" "${PACKAGE}" "${VERSION}"; then
      stable=$(( stable + 1 ))
      echo "Stable poll ${stable}/${STABLE_POLLS}"
      if (( stable >= STABLE_POLLS )); then
        echo "PyPI index ready: ${PACKAGE}==${VERSION}"
        exit 0
      fi
    else
      stable=0
    fi
  else
    stable=0
    echo "PyPI ${PACKAGE}==${VERSION} not indexed yet"
  fi
  sleep "${INTERVAL}"
done

echo "timeout waiting for ${PACKAGE}==${VERSION} on PyPI" >&2
exit 1
