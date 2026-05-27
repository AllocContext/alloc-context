# Host operations (optional self-host)

Reference for running AllocContext timers on a Linux host. For a lighter path,
use the local CLI from the [README](../README.md).

See [docs/self-hosting.md](../docs/self-hosting.md) for layout, secrets, and CI
notes.

## systemd timers

| Timer | Cadence |
|-------|---------|
| `alloc-context-ingest` | Hourly |
| `alloc-context-mcp-http` | On boot (public HTTP MCP, optional x402) |
| `alloc-context-mcp-internal` | On boot (optional loopback MCP, no x402) |

```bash
systemctl list-timers 'alloc-context-*' --no-pager
journalctl -u alloc-context-ingest.service -n 30 --no-pager
journalctl -u alloc-context-mcp-http.service -n 30 --no-pager
```

## Verify

```bash
cd /path/to/alloc-context
source .venv/bin/activate
python -m alloccontext status
python -m alloccontext rollup --scope daily --stdout
curl -s http://127.0.0.1:8000/health
```

## SQLite backup

Nightly timer `alloc-context-backup.timer` (04:15 UTC) runs
`deploy/backup-sqlite.sh`. Backups live under `${TRADING_ROOT}/backups/` with
`manifest.json` per run. See [vps-layout.md](vps-layout.md) for paths; use
`restore-sqlite.sh` and off-host `rsync` of `/opt/trading/backups/` for DR.

```bash
systemctl list-timers 'alloc-context-backup*' --no-pager
sudo -u trading /opt/trading/alloc-context/deploy/backup-sqlite.sh
```

## Rollback

```bash
systemctl disable --now alloc-context-ingest.timer \
  alloc-context-mcp-http.service alloc-context-mcp-internal.service
```

Redeploy a known-good commit or restore from backup:

```bash
sudo bash /opt/trading/alloc-context/deploy/restore-sqlite.sh \
  /opt/trading/backups/YYYYMMDDTHHMMSSZ
```
