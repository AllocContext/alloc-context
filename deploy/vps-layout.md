# Example host layout

Generic paths for optional self-hosting. Adjust to your environment.

```text
/opt/alloc-context/
  .venv/
  config/config.yaml          # from config.example.yaml on first install
  state/
    alloccontext.db
    briefs/
      daily/
      weekly/
  deploy/
    systemd/
```

Secrets: environment file or `.env` on the host (mode 600), not in git.

See [docs/self-hosting.md](../docs/self-hosting.md) and [vps-setup.md](vps-setup.md).
