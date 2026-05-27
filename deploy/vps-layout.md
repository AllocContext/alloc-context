# Example host layout

Generic paths for optional self-hosting with alloc-context-operator. Adjust to
your environment.

```text
/opt/trading/
  shared/.env                 # ALLOC_CONTEXT_* + operator secrets
  alloc-context/
    .venv/
    config/config.yaml
    state/alloccontext.db
    deploy/systemd/
  alloc-context-operator/
    .venv/
    config/config.yaml
    state/operator.db
    state/briefs/daily/
    state/briefs/weekly/
```

Secrets: shared environment file (mode 640, owned by service user), not in git.

See [docs/self-hosting.md](../docs/self-hosting.md), [vps-setup.md](vps-setup.md),
and [alloc-context-operator setup](https://github.com/negillett/alloc-context-operator/blob/main/docs/setup.md).
