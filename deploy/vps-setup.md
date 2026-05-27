# Host operations (optional self-host)

Reference for running AllocContext timers on a Linux host. For a lighter path,
use the local CLI from the [README](../README.md).

See [docs/self-hosting.md](../docs/self-hosting.md) for layout, secrets, and CI
notes.

## systemd timers

| Timer | Cadence |
|-------|---------|
| `alloc-context-ingest` | Hourly |
| `alloc-context-daily-brief` | From `config/config.yaml` |
| `alloc-context-weekly-brief` | From `config/config.yaml` |

```bash
systemctl list-timers 'alloc-context-*' --no-pager
journalctl -u alloc-context-ingest.service -n 30 --no-pager
journalctl -u alloc-context-daily-brief.service -n 30 --no-pager
```

## Verify

```bash
cd /path/to/alloc-context
source .venv/bin/activate
python -m alloccontext status
python -m alloccontext brief daily --stdout
```

## Rollback

```bash
systemctl disable --now alloc-context-ingest.timer \
  alloc-context-daily-brief.timer alloc-context-weekly-brief.timer
```

Redeploy a known-good commit or restore from backup.
