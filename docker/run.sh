#!/usr/bin/env bash
# Run alloc-context CLI in the compose stack (ingest, status, etc.).
set -euo pipefail
# shellcheck source=docker/_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_docker
exec docker compose run --rm mcp "$@"
