# Self-hosting

AllocContext ships as a **library, CLI, and MCP server** for local use.
Running scheduled ingest on your machine keeps the MCP cache warm.

Email, LLM synthesis, band alerts, and similar delivery workflows are **not**
part of this repository.

## Local CLI

See the [README](../README.md) quick start. Layout under the repo checkout:

```text
alloc-context/
  .env                 # secrets (copy from .env.example)
  config/config.yaml   # copy from config.example.yaml
  state/alloccontext.db
```

Run ingest before MCP sessions when you want fresh facts:

```bash
source .env
python -m alloccontext --config config/config.yaml ingest
```

**Loopback HTTP MCP (orchestrator):** `./scripts/local-up.sh` — ingest + MCP on
`:8001` (no x402). `./scripts/local-down.sh` to stop.

**Docker Compose (local evaluation):** `./docker/up.sh` or
[docker-self-host.md](docker-self-host.md) — HTTP MCP on loopback `:8000`,
on-demand ingest, no systemd.

## Linux host + systemd (advanced)

Example layout:

```text
/opt/trading/
  shared/.env                      # secrets for alloc-context
  alloc-context/                   # git checkout or CI rsync target
    config/config.yaml
    state/alloccontext.db
deploy/systemd/                    # ingest timer + public MCP HTTP unit
```

1. Copy `config/config.example.yaml` → `config/config.yaml`.
2. Set secrets via environment or a shared `.env` (Kraken read-only, optional feed
   keys for ingest). See [Shared environment](#shared-environment) below.
3. Install ingest units from `deploy/systemd/`.
4. Or run `deploy/remote-install.sh` on the host after rsync (creates venv,
   installs package, enables ingest timer, restarts HTTP MCP if configured).

### Shared environment

Point systemd units at your env file via `ALLOC_CONTEXT_ENV_FILE` at install
time (example: `/opt/trading/shared/.env`).

| Variable | Example | Purpose |
|----------|---------|---------|
| `ALLOC_CONTEXT_CONFIG` | `/opt/trading/alloc-context/config/config.yaml` | Core config path |
| `ALLOC_CONTEXT_DB` | `/opt/trading/alloc-context/state/alloccontext.db` | SQLite cache (overrides YAML) |

Systemd units assume `WorkingDirectory` and `EnvironmentFile` paths you
configure — edit the `.service` files or override with drop-ins for your layout.

| Timer | Service | Purpose |
|-------|---------|---------|
| Hourly | ingest | Refresh SQLite cache for MCP context tools |

Run MCP separately (stdio via [cursor-mcp.md](cursor-mcp.md), loopback HTTP via
`./scripts/local-up.sh`, or optional HTTP + x402 — [mcp-http.md](mcp-http.md)).

## CI release

Production **VPS deploy has been removed** from the release workflow. Releases
publish to **PyPI** and the **MCP Registry** (PyPI stdio package listing for
self-host — no hosted URL). Self-host via `pip install alloc-context`.

Historical VPS layout and systemd units remain in `deploy/` for operators who
run their own Linux host.
