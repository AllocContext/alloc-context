# Docker self-host stack (Track C)

Evaluate the full ingest + HTTP MCP path with **Docker Compose** — no systemd,
no venv on the host. **v1** ships HTTP MCP and **on-demand ingest** only;
scheduled ingest in compose is a **v2** follow-up.

> **Not for public WAN exposure.** The stack sets `ALLOC_CONTEXT_SELF_HOST_HTTP=1`
> so HTTP can bind `0.0.0.0` inside the container without x402. Publish only on
> loopback (`127.0.0.1:8000`) or place x402 in front for production. See
> [mcp-http.md](mcp-http.md).

> **Privacy:** nothing stored · one-time read-only · pass-through only.

Default quickstart: [agent-onramp.md](agent-onramp.md) (stdio bridge). Use this
doc when you want to **evaluate self-host HTTP + SQLite** in one command.

## Prerequisites

- Docker Engine + Compose v2
- Git clone of [AllocContext/alloc-context](https://github.com/AllocContext/alloc-context)

## Quick start

```bash
cd alloc-context
docker compose up --build -d
docker compose run --rm mcp ingest
curl -sf http://127.0.0.1:8000/health | python3 -m json.tool
```

First ingest runs with **all sources disabled** in `config/config.docker.yaml`.
The MCP server starts immediately; enable feeds and add keys before expecting
market context in tool output.

### Enable sources

Edit `config/config.docker.yaml` → `ingest.sources` (set desired feeds to
`true`). Keyless feeds: `fear_greed`, `kalshi`, `macro_calendar`. Keyed feeds
need `docker/.env` (see below).

```bash
cp docker/.env.example docker/.env
# edit docker/.env — never commit
# edit config/config.docker.yaml — enable matching ingest.sources
docker compose run --rm mcp ingest
docker compose up -d
```

| Source | Config flag | Typical env var |
|--------|-------------|-----------------|
| Kraken | `kraken: true` + `exchanges.kraken.enabled` | `KRAKEN_API_*` |
| Coinbase | `coinbase: true` + `exchanges.coinbase.enabled` | `COINBASE_API_*` |
| FRED macro | `fred: true` | `FRED_API_KEY` |
| CoinGecko | `coingecko: true` | optional (`use_demo_key: true`) |
| CoinMarketCap | `coinmarketcap: true` | `COINMARKETCAP_API_KEY` |
| ETF flows | `etf_flows: true` + `etf.sosovalue_enabled` | `SOSOVALUE_API_KEY` |
| Fear & Greed | `fear_greed: true` | — |
| Kalshi | `kalshi: true` | — |

## MCP endpoint

| | |
|--|--|
| Health | `GET http://127.0.0.1:8000/health` |
| MCP | `POST http://127.0.0.1:8000/mcp` (streamable HTTP) |

Example initialize (no payment gate in this stack):

```bash
curl -s http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

After ingest, call `get_market_context` or `get_context_bundle` via your MCP
client. Tool args: [mcp.md](mcp.md).

## On-demand ingest

**v1** does not run a cron/timer in compose. Refresh SQLite when you want new
facts:

```bash
docker compose run --rm mcp ingest
```

Dry run:

```bash
docker compose run --rm mcp ingest --dry-run
```

Status (includes MCP health when the `mcp` service is up):

```bash
docker compose run --rm mcp status --mcp-url http://mcp:8000/health
```

## Stdio via Docker (optional)

For Cursor stdio instead of HTTP, run interactively:

```bash
docker build -t alloc-context:local .
docker run -i --rm \
  -v alloc-context-data:/data \
  -e ALLOC_CONTEXT_CONFIG=/app/config/config.docker.yaml \
  -e ALLOC_CONTEXT_DB=/data/alloccontext.db \
  alloc-context:local \
  mcp --transport stdio
```

Mount your own `config/config.yaml` when moving beyond the docker defaults.

## Layout

| Path | Purpose |
|------|---------|
| `Dockerfile` | Pinned `python:3.11-slim-bookworm`; installs `.[hosted]` |
| `docker-compose.yml` | `mcp` service, SQLite volume `alloc-data` |
| `config/config.docker.yaml` | All ingest sources off by default; opt-in when keyed |
| `docker/.env.example` | Optional ingest API keys |

SQLite lives in the `alloc-data` volume at `/data/alloccontext.db`.

## Production self-host

For Linux + systemd, VPS deploy, and x402 on a public URL, see
[self-hosting.md](self-hosting.md) and [publishing.md](publishing.md). This
compose stack is for **local evaluation** only — not a substitute for the
release workflow or operator delivery layer.

## Related

- [agent-onramp.md](agent-onramp.md) — default ~2 min path (stdio / hosted x402)
- [local-dev.md](local-dev.md) — native venv dev stack (no Docker)
- [mcp-http.md](mcp-http.md) — x402 and production HTTP MCP
