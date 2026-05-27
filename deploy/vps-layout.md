# Example host layout

Generic paths for optional self-hosting. Adjust to your environment.

```text
/opt/trading/
  shared/.env                 # ALLOC_CONTEXT_* and data API keys
  backups/                    # SQLite backups (manifest.json per run)
  alloc-context/
    .venv/
    config/config.yaml
    state/alloccontext.db
    deploy/systemd/
  alloc-context-operator/
    state/operator.db
```

Secrets: shared environment file (mode 640, owned by service user), not in git.

See [docs/self-hosting.md](../docs/self-hosting.md) and [vps-setup.md](vps-setup.md).
