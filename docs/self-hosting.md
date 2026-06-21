# Self-hosting (optional)

AllocContext ships as a **library, CLI, and MCP server** for local evaluation.
Running scheduled ingest on your own Linux host keeps the MCP cache warm; it is
not required for consumers of a hosted MCP endpoint.

Email, LLM synthesis, band alerts, and similar delivery workflows are **not**
part of this repository.

## Local CLI

See the [README](../README.md) quick start. You need your own API keys in
`.env` (never commit) and a copy of `config/config.yaml`.

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
   installs package, enables ingest timer, restarts public MCP).

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

Run MCP separately (stdio bridge via [cursor-mcp.md](cursor-mcp.md), self-host
stdio, or HTTP + x402 for agents). See
[docs/mcp-http.md](mcp-http.md).

## CI release

Production **VPS deploy has been removed** from the release workflow. Releases
publish to PyPI and the MCP Registry only. Self-host via `pip install alloc-context`.

Historical VPS layout and systemd units remain in `deploy/` for operators who
run their own Linux host.
