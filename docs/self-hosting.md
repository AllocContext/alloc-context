# Self-hosting (optional)

AllocContext ships as a **library and CLI** for local evaluation. Running a
scheduled ingest + email pipeline on your own Linux host is supported but not
the primary product path — see [mcp-roadmap.md](mcp-roadmap.md) for the
agent-native API direction.

## Local CLI

See the [README](../README.md) quick start. You need your own API keys in
`.env` (never commit) and a copy of `config/config.yaml`.

## Linux host + systemd (advanced)

Example layout:

```text
/opt/alloc-context/          # git checkout or CI rsync target
  config/config.yaml
  state/alloccontext.db
deploy/systemd/              # alloc-context-*.service / *.timer
```

1. Copy `config/config.example.yaml` → `config/config.yaml`.
2. Set secrets via environment or `.env` (Kraken read-only, optional feed
   keys, OpenAI for LLM briefs, Resend for email).
3. Install units from `deploy/systemd/` and run
   `deploy/render-systemd-timers.py` to bake schedule from config.
4. Or run `deploy/remote-install.sh` on the host after rsync (creates venv,
   installs package, enables timers).

Systemd units assume `WorkingDirectory` and `EnvironmentFile` paths you
configure — edit the `.service` files or override with drop-ins for your layout.

## CI deploy (maintainer)

The upstream repository may run an optional GitHub Actions **deploy** job after
tests pass on `main`. It requires repository secrets:

| Secret | Required | Purpose |
|--------|----------|---------|
| `VPS_SSH_KEY` | Yes | Private key for SSH/rsync |
| `VPS_HOST` | Yes | Hostname or IP (not logged in workflow output) |
| `VPS_USER` | No | SSH user (default `root`) |

Application secrets (Kraken, OpenAI, email, data APIs) stay on the host — not
in GitHub.

Optional repository **variables** (Settings → Secrets and variables → Actions →
Variables) for non-secret deploy paths:

| Variable | Example | Purpose |
|----------|---------|---------|
| `ALLOC_CONTEXT_REMOTE` | `/opt/trading/alloc-context` | Rsync + systemd install root |
| `ALLOC_CONTEXT_ENV_FILE` | `/opt/trading/shared/.env` | systemd `EnvironmentFile` |

If unset, defaults are `${REMOTE}/.env` and `/opt/alloc-context`.

**Break-glass rsync** (no baked-in host or key):

```bash
VPS_HOST=your.host.example SSH_KEY=~/.ssh/deploy_key ./deploy/rsync-to-vps.sh
```

Set `ALLOC_CONTEXT_REMOTE` and optional `ALLOC_CONTEXT_ENV_FILE` when running
`deploy/remote-install.sh` if your paths differ from the generic unit templates.

The deploy job is gated to the canonical repository only; forks run tests only.
