# AllocContext

**Allocation context for BTC/ETH** — drift, band checks, USD rebalance moves,
and a fused market backdrop (Fear & Greed, Kalshi, ETF flows, macro) as
deterministic JSON over MCP.

The product is an **agent-native MCP API** with x402 pay-per-call on Base —
see [docs/mcp.md](docs/mcp.md).

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
| [docs/cursor-mcp.md](docs/cursor-mcp.md) | Cursor stdio MCP |
| [docs/context-bundle.md](docs/context-bundle.md) | ContextBundle schema |
| [docs/architecture.md](docs/architecture.md) | Pipeline and trust boundaries |
| [docs/data-sources.md](docs/data-sources.md) | Ingest sources |
| [docs/self-hosting.md](docs/self-hosting.md) | Optional Linux/systemd ingest + MCP |

## Contributing

GitHub Issues are welcome for bugs, schema feedback, and MCP API suggestions.
Unsolicited pull requests are not expected — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
