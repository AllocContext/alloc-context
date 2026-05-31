# AllocContext

mcp-name: io.github.negillett/alloc-context

**Allocation context for BTC/ETH** — drift, band checks, USD rebalance moves,
and a fused market backdrop (Fear & Greed, Kalshi, ETF flows, macro) as
deterministic JSON over MCP.

The product is an **agent-native MCP API** with x402 pay-per-call on Base —
see [docs/mcp.md](docs/mcp.md).

## Hosted MCP (production)

Try the public endpoint without self-hosting:

| | |
|--|--|
| **URL** | `https://mcp.alloc-context.com/mcp` |
| **Discovery** | [llms.txt](https://mcp.alloc-context.com/llms.txt), [x402 manifest](https://mcp.alloc-context.com/.well-known/x402.json) |
| **Pricing** | **$0.02** cached context/math · **$0.05** live ingest or portfolio |
| **Payment** | x402 on Base — USDC or EURC |

Agents find the service via [CDP Bazaar](docs/mcp-discovery.md). Integration
guide: [docs/agent-integration.md](docs/agent-integration.md). Example JSON:
[docs/examples.md](docs/examples.md).

**Try free locally** (no payment): `./scripts/dev-up.sh` — see
[docs/local-dev.md](docs/local-dev.md).

Optional live portfolio reads use read-only exchange credentials passed in
each request. Not financial advice.

```text
ingest → store → rollup → MCP tools (+ optional x402 HTTP)
```

This package is **facts and MCP only** — ingest, rollups, and agent tools.
Email, LLM synthesis, and alert delivery are out of scope for this repository.

## Try it locally

```bash
git clone git@github.com:negillett/alloc-context.git
cd alloc-context
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # fill locally; never commit
cp config/config.example.yaml config/config.yaml

python -m alloccontext ingest --dry-run
python -m alloccontext rollup --scope daily --stdout
pytest
```

**MCP (stdio):** `pip install -e ".[mcp]"` then `alloc-context mcp`.
See [docs/cursor-mcp.md](docs/cursor-mcp.md).

**Hosted MCP + x402:** `pip install -e ".[hosted]"` then
`alloc-context mcp --transport http --x402`. See [docs/mcp-http.md](docs/mcp-http.md).

**Local dev stack (internal MCP on :8001):** `./scripts/dev-up.sh`.
See [docs/local-dev.md](docs/local-dev.md).

CLI entry point: `alloc-context` (same as `python -m alloccontext`).

## Commands

| Command | Purpose |
|---------|---------|
| `python -m alloccontext ingest` | Pull configured sources → SQLite |
| `python -m alloccontext rollup --scope daily --stdout` | ContextBundle JSON (facts) |
| `python -m alloccontext status` | Per-source ingest ages, snapshots, MCP `/health` |
| `alloc-context mcp` | MCP server (stdio or HTTP) |

## MCP tools

| Tool | Purpose |
|------|---------|
| `get_context_bundle` | Full ContextBundle — portfolio, market, sentiment, macro, delta, regime |
| `get_market_context` | Sentiment, macro, ETF, breadth, and market fields (no portfolio) |
| `get_context_at` | Saved snapshot from ingest history at a given `as_of` |
| `get_context_delta` | Notable shifts between two saved snapshots |
| `get_rebalance_plan` | USD rebalance moves from allocation, target, and NAV |
| `check_allocation_band` | Drift vs target and whether allocation is outside the band |
| `check_allocation_bands` | Batch band checks for multiple target scenarios |
| `get_portfolio_state` | Live NAV and allocation from Kraken or Coinbase (credentials in request) |

See [docs/mcp.md](docs/mcp.md) for arguments, pricing, and resources.

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/mcp.md](docs/mcp.md) | MCP tools and x402 |
| [docs/mcp-http.md](docs/mcp-http.md) | HTTP MCP + x402 setup |
| [docs/mcp-discovery.md](docs/mcp-discovery.md) | Bazaar and agent discovery |
| [docs/distribution.md](docs/distribution.md) | GitHub, PyPI, MCP Registry, directories |
| [docs/agent-integration.md](docs/agent-integration.md) | Paid HTTP MCP + Bazaar for agents |
| [docs/cursor-mcp.md](docs/cursor-mcp.md) | Cursor stdio MCP |
| [docs/examples.md](docs/examples.md) | Sample tool JSON (redacted) |
| [docs/context-bundle.md](docs/context-bundle.md) | ContextBundle schema |
| [docs/architecture.md](docs/architecture.md) | Pipeline and trust boundaries |
| [docs/data-sources.md](docs/data-sources.md) | Ingest sources |
| [docs/self-hosting.md](docs/self-hosting.md) | Optional Linux/systemd ingest + MCP |
| [docs/local-dev.md](docs/local-dev.md) | Local internal MCP + dev ingest |
| [docs/USE.md](docs/USE.md) | Self-host vs hosted MCP (plain language) |
| [docs/user-config.md](docs/user-config.md) | Bridge `user.yaml` reference |

## Contributing

GitHub Issues are welcome for bugs, schema feedback, and MCP API suggestions.
Unsolicited pull requests are not expected — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Elastic License 2.0](LICENSE) — source-available, self-host friendly. See
[docs/USE.md](docs/USE.md) for plain-language allowed uses.

**Official hosted MCP:** `https://mcp.alloc-context.com/mcp`
