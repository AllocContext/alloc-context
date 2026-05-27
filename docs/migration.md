# Migration from market-analyst

AllocContext was renamed from **market-analyst** (May 2026).

| Before | After |
|--------|-------|
| Package `analyst/` | `alloccontext/` |
| `python -m analyst` | `python -m alloccontext` |
| CLI `market-analyst` | `alloc-context` |
| `MARKET_ANALYST_*` env | `ALLOC_CONTEXT_*` (legacy env still works) |
| Default DB `state/analyst.db` | `state/alloccontext.db` |
| systemd `market-analyst-*` | `alloc-context-*` |

## Local checkout

```bash
pip install -e ".[dev]"
```

Update scripts and aliases to `python -m alloccontext`.

## Self-hosted deploy

If you run timers on a Linux host, `deploy/remote-install.sh` disables old
`market-analyst-*.timer` units when present and enables `alloc-context-*`.
See [self-hosting.md](self-hosting.md).

## GitHub

Repository renamed to **alloc-context**. Update your remote:

```bash
git remote set-url origin git@github.com:YOUR_ORG/alloc-context.git
```
