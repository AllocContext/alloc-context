#!/usr/bin/env bash
# Start the Docker self-host stack (HTTP MCP + SQLite volume).
set -euo pipefail
# shellcheck source=docker/_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_docker

echo "Building and starting alloc-context docker stack..."
docker compose up --build -d --wait

if [[ "${SKIP_DOCKER_INGEST:-}" != "1" ]]; then
  echo "Running ingest..."
  docker compose run --rm mcp ingest
fi

cat <<EOF
Docker stack ready.

  Health: http://127.0.0.1:8000/health
  MCP:    http://127.0.0.1:8000/mcp
  Config: ${DOCKER_DIR}/config.yaml
  Data:   alloc-context_alloc-data volume

  Stop:   ./docker/down.sh
  CLI:    ./docker/run.sh ingest | status | ...
  Docs:   docs/docker-self-host.md
EOF
