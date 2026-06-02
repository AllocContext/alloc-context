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

## CI release and deploy

Production VPS deploys run from the **release** workflow — either
**workflow_dispatch** (recommended) or a manual `vX.Y.Z` tag push. The same
workflow publishes to PyPI. See [publishing.md](publishing.md).

| Repo | `main` push | Production deploy |
|------|-------------|-------------------|
| `alloc-context` | Tests only (`ci`) | **release** workflow |
| `alloc-context-operator` | Tests + deploy (`ci`) | On every `main` merge |

Release deploy requires repository secrets:

| Secret | Required | Purpose |
|--------|----------|---------|
| `VPS_SSH_KEY` | Yes | Private key for SSH/rsync |
| `VPS_HOST` | Yes | Hostname or IP (not logged in workflow output) |
| `VPS_USER` | No | SSH user (default `root`) |
| `EVM_PRIVATE_KEY` | Paid smoke only | Buyer wallet for weekly x402 settlement ([mcp-discovery.md](mcp-discovery.md)) |

Application secrets (Kraken, data APIs, seller x402 keys) stay on the host — not in GitHub.

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

Release deploy runs only on the primary GitHub repository; forks run tests
only.

After install, CI runs the operator `smoke` command on the VPS via
`deploy/run-vps-smoke.sh` (health checks plus cached `get_context_bundle`).
When `X402_ENABLED=true` in the shared env file, CI also runs
`deploy/run-vps-x402-check.sh` (discovery URLs, manifest, 402 gate, CDP
facilitator when configured). Smoke or x402 failure marks the deploy job red
but does not roll back rsync or systemd changes. Set
`ALLOC_CONTEXT_OPERATOR_REMOTE` if the operator checkout path differs from
`/opt/trading/alloc-context-operator`.
