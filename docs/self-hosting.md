# Self-hosting (optional)

AllocContext ships as a **library, CLI, and MCP server** for local evaluation.
Running scheduled ingest on your own Linux host keeps the MCP cache warm; it is
not required for consumers of a hosted MCP endpoint.

Email, LLM synthesis, band alerts, and similar delivery workflows are **not**
part of this repository.

## Local CLI

See the [README](../README.md) quick start. You need your own API keys in
`.env` (never commit) and a copy of `config/config.yaml`.

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

Run MCP separately (stdio for Cursor, or HTTP + x402 for agents). See
[docs/mcp-http.md](mcp-http.md).

## CI deploy

The repository may run an optional GitHub Actions **deploy** job after
tests pass on `main`. It requires repository secrets:

| Secret | Required | Purpose |
|--------|----------|---------|
| `VPS_SSH_KEY` | Yes | Private key for SSH/rsync |
| `VPS_HOST` | Yes | Hostname or IP (not logged in workflow output) |
| `VPS_USER` | No | SSH user (default `root`) |

Application secrets (Kraken, data APIs) stay on the host — not in GitHub.

Optional repository **variables** (Settings → Secrets and variables → Actions →
Variables) for non-secret deploy paths:

| Variable | Example | Purpose |
|----------|---------|---------|
| `ALLOC_CONTEXT_REMOTE` | `/opt/trading/alloc-context` | Rsync + systemd install root |
| `ALLOC_CONTEXT_OPERATOR_REMOTE` | `/opt/trading/alloc-context-operator` | Operator checkout (post-deploy smoke) |
| `ALLOC_CONTEXT_ENV_FILE` | `/opt/trading/shared/.env` | systemd `EnvironmentFile` |

Template: [deploy/shared.env.example](../deploy/shared.env.example).

If unset, defaults are `${REMOTE}/.env` and `/opt/alloc-context`.

**Break-glass rsync** (no baked-in host or key):

```bash
VPS_HOST=your.host.example SSH_KEY=~/.ssh/deploy_key ./deploy/rsync-to-vps.sh
```

Set `ALLOC_CONTEXT_REMOTE` and optional `ALLOC_CONTEXT_ENV_FILE` when running
`deploy/remote-install.sh` if your paths differ from the generic unit templates.

The deploy job runs only on the primary GitHub repository; forks run tests only.

After install, CI runs the operator `smoke` command on the VPS via
`deploy/run-vps-smoke.sh` (health checks plus cached `get_context_bundle`).
Smoke failure marks the deploy job red but does not roll back rsync or systemd
changes. Set `ALLOC_CONTEXT_OPERATOR_REMOTE` if the operator checkout path
differs from `/opt/trading/alloc-context-operator`.
