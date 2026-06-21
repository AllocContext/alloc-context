# Local development stack

One-command loopback MCP for core development and HTTP client testing without
x402.

## Quick start

```bash
cd alloc-context
chmod +x scripts/dev-up.sh scripts/dev-down.sh   # once, if needed
./scripts/dev-up.sh
```

This will:

1. Create/use `.venv` and `pip install -e ".[dev]"`
2. Run ingest with [`config/config.dev.yaml`](../config/config.dev.yaml) (no exchange keys)
3. Start HTTP MCP on **127.0.0.1:8001** without x402 (matches production internal port)

Stop the server:

```bash
./scripts/dev-down.sh
```

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `ALLOC_CONTEXT_CONFIG` | `config/config.dev.yaml` | Dev ingest + MCP config |
| `DEV_MCP_HOST` | `127.0.0.1` | HTTP bind address |
| `DEV_MCP_PORT` | `8001` | HTTP port (loopback MCP listener) |
| `SKIP_DEV_INGEST` | unset | Set to `1` to restart MCP without re-ingesting |

Dev config uses public sources only (Kalshi, Fear & Greed, CoinGecko demo, etc.).
Exchange portfolio ingest is off until you enable it in config and add keys to
`.env`.

## Verify

```bash
curl -sf http://127.0.0.1:8001/health | python3 -m json.tool

python -m alloccontext --config config/config.dev.yaml status \
  --mcp-url http://127.0.0.1:8001/health

curl -s http://127.0.0.1:8001/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

## HTTP client testing

Point any MCP HTTP client at the dev listener, for example:

```yaml
mcp:
  url: http://127.0.0.1:8001/mcp
```

Verify tool calls with curl or your agent client against loopback facts.

## Logs and state

| Path | Purpose |
|------|---------|
| `state/dev/alloccontext.db` | Dev SQLite (separate from `state/alloccontext.db`) |
| `state/dev-mcp.log` | MCP server stdout/stderr |
| `state/dev-mcp.pid` | Background MCP pid |

## Troubleshooting

- **Ingest fails:** check network; optional API keys in `.env` improve macro/ETF
  coverage. If `state/dev/alloccontext.db` already exists, dev-up continues with
  a warning; otherwise ingest must succeed on first run.
- **Wrong config from `.env`:** dev-up forces `ALLOC_CONTEXT_CONFIG` to
  `config/config.dev.yaml` (or your override) so MCP and ingest stay aligned.
- **Port in use:** `DEV_MCP_PORT=8002 ./scripts/dev-up.sh` and point clients at the new port.
- **Stale process:** `./scripts/dev-down.sh` then `./scripts/dev-up.sh`

## Docker alternative

Prefer containers over a host venv: `./docker/up.sh` — see
[docker-self-host.md](docker-self-host.md) (`:8000`, same keyless ingest idea).
