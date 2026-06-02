#!/usr/bin/env bash
# Start the Docker self-host stack (HTTP MCP + SQLite volume).
set -euo pipefail

DOCKER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${DOCKER_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required" >&2
  exit 1
fi

echo "Building and starting alloc-context docker stack..."
docker compose up --build -d

if [[ "${SKIP_DOCKER_INGEST:-}" != "1" ]]; then
  echo "Running ingest..."
  docker compose run --rm mcp ingest
fi

if command -v curl >/dev/null 2>&1; then
  ready=0
  for _ in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8000/health >/dev/null; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "${ready}" -ne 1 ]]; then
    echo "error: MCP did not become healthy on http://127.0.0.1:8000/health" >&2
    echo "       check: docker compose logs mcp" >&2
    exit 1
  fi
fi

cat <<EOF
Docker stack ready.

  Health: http://127.0.0.1:8000/health
  MCP:    http://127.0.0.1:8000/mcp
  Config: ${DOCKER_DIR}/config.yaml
  Data:   alloc-context_alloc-data volume

  Stop:   docker/down.sh
  Ingest: docker compose run --rm mcp ingest   (from ${DOCKER_DIR})
  Docs:   docs/docker-self-host.md
EOF
