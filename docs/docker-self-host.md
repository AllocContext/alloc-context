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
doc when you want to **evaluate self-host HTTP + SQLite** without a host venv.

## Prerequisites

- Docker Engine + Compose v2
- Git clone of [AllocContext/alloc-context](https://github.com/AllocContext/alloc-context)

## Quick start

```bash
cd alloc-context/docker
docker compose up --build -d
docker compose run --rm mcp ingest
curl -sf http://127.0.0.1:8000/health | python3 -m json.tool
```

First ingest pulls **keyless public sources** (Kalshi, Fear & Greed, macro
calendar, CoinGecko demo). Exchange portfolio reads and other **keyed optional
feeds** stay off until you add credentials (below).

### Enable keyed sources

Edit `docker/config.yaml` → `ingest.sources` and add keys in `.env` for feeds
that require credentials. Keyless feeds are already on by default. Compose
mounts `config.yaml` into the container — edits apply on the next ingest without
rebuild. Restart the service after changing `.env` (`docker compose up -d`).

```bash
cd alloc-context/docker
cp .env.example .env
# edit .env — never commit
# edit config.yaml — enable matching ingest.sources
docker compose run --rm mcp ingest
docker compose up -d
```

| Source | Default | Config flag | Typical env var |
|--------|---------|-------------|-----------------|
| Fear & Greed | on | `fear_greed: true` | — |
| Kalshi | on | `kalshi: true` | — |
| Macro calendar | on | `macro_calendar: true` | — |
| CoinGecko | on | `coingecko: true` | optional (`use_demo_key: true`) |
| Kraken | off | `kraken: true` + `exchanges.kraken.enabled` | `KRAKEN_API_*` |
| Coinbase | off | `coinbase: true` + `exchanges.coinbase.enabled` | `COINBASE_API_*` |
| FRED macro | off | `fred: true` | `FRED_API_KEY` |
| CoinMarketCap | off | `coinmarketcap: true` | `COINMARKETCAP_API_KEY` |
| ETF flows | off | `etf_flows: true` + `etf.sosovalue_enabled` | `SOSOVALUE_API_KEY` |

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
cd alloc-context/docker
docker compose run --rm mcp ingest
```

Dry run:

```bash
cd alloc-context/docker
docker compose run --rm mcp ingest --dry-run
```

Status (includes MCP health when the `mcp` service is up):

```bash
cd alloc-context/docker
docker compose run --rm mcp status --mcp-url http://mcp:8000/health
```

## Stdio via Docker (optional)

For Cursor stdio instead of HTTP, run interactively from the repo root:

```bash
docker build -f docker/Dockerfile -t alloc-context:local .
docker run -i --rm \
  -v alloc-context-data:/data \
  -v "$(pwd)/docker/config.yaml:/app/docker/config.yaml:ro" \
  -e ALLOC_CONTEXT_CONFIG=/app/docker/config.yaml \
  -e ALLOC_CONTEXT_DB=/data/alloccontext.db \
  alloc-context:local \
  mcp --transport stdio
```

Edit `docker/config.yaml` on the host before run; the mount keeps stdio in sync
with compose. Use a different config path when moving beyond the docker defaults.

## Layout

All stack artifacts live under `docker/`:

| Path | Purpose |
|------|---------|
| `docker/Dockerfile` | Pinned `python:3.11-slim-bookworm`; installs `.[hosted]` |
| `docker/compose.yml` | `mcp` service; mounts `config.yaml`; volume `alloc-data` |
| `docker/config.yaml` | Keyless ingest on; keyed optional sources off (live-mounted) |
| `docker/.env.example` | Optional ingest API keys |

SQLite lives in the `alloc-context_alloc-data` volume at `/data/alloccontext.db`.

## Production self-host

For Linux + systemd, VPS deploy, and x402 on a public URL, see
[self-hosting.md](self-hosting.md) and [publishing.md](publishing.md). This
compose stack is for **local evaluation** only — not a substitute for the
release workflow or operator delivery layer.

## Related

- [agent-onramp.md](agent-onramp.md) — default ~2 min path (stdio / hosted x402)
- [local-dev.md](local-dev.md) — native venv dev stack (no Docker)
- [mcp-http.md](mcp-http.md) — x402 and production HTTP MCP
