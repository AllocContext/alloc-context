#!/usr/bin/env bash
# Stop the Docker self-host stack started by docker/up.sh.
set -euo pipefail
# shellcheck source=docker/_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_docker

if [[ "${1:-}" == "--volumes" ]]; then
  docker compose down --volumes
  echo "Stopped stack and removed alloc-context_alloc-data volume."
  exit 0
fi

docker compose down
echo "Stopped stack (SQLite volume preserved). Use down.sh --volumes to remove data."
