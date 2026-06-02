#!/usr/bin/env bash
# Stop the Docker self-host stack started by docker/up.sh.
set -euo pipefail

DOCKER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${DOCKER_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required" >&2
  exit 1
fi

if [[ "${1:-}" == "--volumes" ]]; then
  docker compose down --volumes
  echo "Stopped stack and removed alloc-context_alloc-data volume."
  exit 0
fi

docker compose down
echo "Stopped stack (SQLite volume preserved). Use down.sh --volumes to remove data."
