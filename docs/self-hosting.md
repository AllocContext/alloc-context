# Self-hosting (optional)

AllocContext ships as a **library, CLI, and MCP server** for local evaluation.
Running scheduled ingest on your own Linux host keeps the MCP cache warm; it is
not required for consumers of a hosted MCP endpoint.

Email briefs, band alerts, and LLM digests are **not** part of this repo.
Deploy them from [alloc-context-operator](https://github.com/negillett/alloc-context-operator)
against your MCP URL (local HTTP or hosted x402).

## Local CLI

See the [README](../README.md) quick start. You need your own API keys in
`.env` (never commit) and a copy of `config/config.yaml`.

## Linux host + systemd (advanced)

Example layout:

```text
/opt/trading/
  shared/.env                      # secrets for core + operator
  alloc-context/                   # git checkout or CI rsync target
    config/config.yaml
    state/alloccontext.db
  alloc-context-operator/          # briefs + alerts (separate repo)
    config/config.yaml
    state/operator.db
deploy/systemd/                    # alloc-context-ingest.service / *.timer
```

1. Copy `config/config.example.yaml` → `config/config.yaml`.
2. Set secrets via environment or a shared `.env` (Kraken read-only, optional feed
   keys for ingest). See [Shared environment](#shared-environment) below.
3. Install ingest units from `deploy/systemd/`.
4. Or run `deploy/remote-install.sh` on the host after rsync (creates venv,
   installs package, enables ingest timer).

### Shared environment

When core and [alloc-context-operator](https://github.com/negillett/alloc-context-operator)
run on one host, point both at the same env file via `ALLOC_CONTEXT_ENV_FILE`
at install time (example: `/opt/trading/shared/.env`).

| Variable | Example | Purpose |
|----------|---------|---------|
| `ALLOC_CONTEXT_CONFIG` | `/opt/trading/alloc-context/config/config.yaml` | Core config path |
| `ALLOC_CONTEXT_DB` | `/opt/trading/alloc-context/state/alloccontext.db` | SQLite cache (overrides YAML) |

Operator-specific keys (`OPENAI_API_KEY`, `RESEND_*`, `EMAIL_TO`) live in the
same shared file; see the operator repo.

Systemd units assume `WorkingDirectory` and `EnvironmentFile` paths you
configure — edit the `.service` files or override with drop-ins for your layout.

| Timer | Service | Purpose |
|-------|---------|---------|
| Hourly | ingest | Refresh SQLite cache for MCP Tier 1 |

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
