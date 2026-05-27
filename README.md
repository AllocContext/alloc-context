# AllocContext

**Allocation context for BTC/ETH** — drift, band checks, USD rebalance moves,
and a fused market backdrop (Fear & Greed, Kalshi, ETF flows, macro) as
deterministic JSON.

The product direction is an **agent-native MCP API** with x402 pay-per-call
discovery — see [docs/mcp-roadmap.md](docs/mcp-roadmap.md). The CLI and
ContextBundle schema in this repo are the foundation.

Read-only exchange access when configured. Not financial advice.

```text
ingest → store → rollup (ContextBundle)
  → MCP tools + x402 (planned)
  → optional: synthesize / email briefs (self-host)
```

## Try it locally

For evaluation and development — bring your own API keys:

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

**MCP (Phase A):** `pip install -e ".[mcp]"` then `alloc-context mcp` (stdio).
See [docs/cursor-mcp.md](docs/cursor-mcp.md).

**Hosted MCP + x402 (Phase B):** `pip install -e ".[hosted]"` then
`alloc-context mcp --transport http --x402`. See [docs/mcp-http.md](docs/mcp-http.md).

CLI entry point: `alloc-context` (same as `python -m alloccontext`).

## Commands

| Command | Purpose |
|---------|---------|
| `python -m alloccontext rollup --scope daily --stdout` | ContextBundle JSON (facts) |
| `python -m alloccontext alerts --stdout` | Allocation band check |
| `python -m alloccontext ingest` | Pull configured sources → SQLite |
| `python -m alloccontext brief daily --stdout` | Brief with optional LLM narrative |
| `python -m alloccontext status` | Ingest freshness, DB path |

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/mcp-roadmap.md](docs/mcp-roadmap.md) | MCP + x402 product plan |
| [docs/mcp-http.md](docs/mcp-http.md) | HTTP MCP + x402 setup |
| [docs/cursor-mcp.md](docs/cursor-mcp.md) | Cursor MCP dogfooding |
| [docs/context-bundle.md](docs/context-bundle.md) | ContextBundle schema |
| [docs/architecture.md](docs/architecture.md) | Pipeline and trust boundaries |
| [docs/data-sources.md](docs/data-sources.md) | Ingest sources |
| [docs/self-hosting.md](docs/self-hosting.md) | Optional Linux/systemd setup |
| [docs/migration.md](docs/migration.md) | Rename from market-analyst |

## Contributing

GitHub Issues are welcome for bugs, schema feedback, and MCP API design.
Unsolicited pull requests are not expected — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
