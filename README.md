# AllocContext

[![smithery badge](https://smithery.ai/badge/alloccontext/alloc-context)](https://smithery.ai/servers/alloccontext/alloc-context)

mcp-name: io.github.AllocContext/alloc-context

**Portfolio-aware crypto context for whatever you hold** — discover your
holdings, holdings-scoped market data, sentiment, macro, and regime; optional
allocation analysis when you supply targets. Deterministic JSON over MCP.

**New here?** [Cursor MCP setup](docs/cursor-mcp.md) — stdio in your editor, or
[self-hosting](docs/self-hosting.md) with local ingest. **Organization:**
[AllocContext on GitHub](https://github.com/AllocContext).

> **Privacy:** nothing stored · one-time read-only · pass-through only when
> using live portfolio reads. See [USE.md](docs/USE.md).

## Quick start (Cursor, self-host)

**1. Install**

```bash
pip install "alloc-context[mcp]"
# From source: pip install -e ".[mcp]"
```

**2. Config and secrets**

Copy [config/config.example.yaml](config/config.example.yaml) to
`config/config.yaml`. Copy [.env.example](.env.example) to `.env` and add
read-only exchange keys when you want portfolio ingest or macro feeds.
See [self-hosting.md](docs/self-hosting.md).

**3. MCP config**

Add to your Cursor `mcp.json` (or project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "alloc-context": {
      "command": "alloc-context",
      "args": [
        "mcp",
        "--config",
        "/absolute/path/to/alloc-context/config/config.yaml"
      ],
      "env": {
        "ALLOC_CONTEXT_DB": "/absolute/path/to/alloc-context/state/alloccontext.db"
      }
    }
  }
}
```

Use absolute paths. See [cursor-mcp.example.json](docs/cursor-mcp.example.json).

**4. Refresh facts (optional)**

```bash
python -m alloccontext --config config/config.yaml ingest
```

Run before a session or when you want fresh macro/regime data. No cron required.

**5. Ask your agent**

Call `get_context_bundle` for a full snapshot. Pure math tools
(`check_allocation_band`, `get_rebalance_plan`) work without portfolio credentials.

Full setup: [cursor-mcp.md](docs/cursor-mcp.md). Samples: [examples.md](docs/examples.md).

Not financial advice.

## MCP tools

| Tool | Purpose |
|------|---------|
| `get_context_bundle` | Full ContextBundle — holdings, market, sentiment, macro, delta, regime; optional `allocation_analysis` |
| `get_market_context` | Sentiment, macro, ETF, breadth, and market fields (no portfolio) |
| `get_context_at` | Saved snapshot from ingest history at a given `as_of` |
| `get_context_delta` | Notable shifts between two saved snapshots |
| `get_rebalance_plan` | USD rebalance moves from allocation, target, and NAV |
| `check_allocation_band` | Drift vs target and whether allocation is outside the band |
| `check_allocation_bands` | Batch band checks for multiple target scenarios |
| `get_portfolio_state` | Live NAV and holdings (CEX keys or public EVM wallet address) |
| `get_expectation_review` | Score optional local theses against context (pass-through) |

Market context is **holdings-scoped**: band assets (BTC/ETH) use OHLC bars; alt
holdings (e.g. HYPE) use quote snapshots when cached. See
[context-bundle.md#market-coverage](docs/context-bundle.md#market-coverage).

See [mcp.md](docs/mcp.md) for arguments and resources.

## Self-host and development

Run ingest and MCP on your machine — the primary supported path.

See [self-hosting.md](docs/self-hosting.md), [local-dev.md](docs/local-dev.md)
(`./scripts/dev-up.sh`), or [docker-self-host.md](docs/docker-self-host.md).

```bash
git clone git@github.com:AllocContext/alloc-context.git
cd alloc-context
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,mcp]"
cp .env.example .env
cp config/config.example.yaml config/config.yaml

python -m alloccontext ingest --dry-run
python -m alloccontext rollup --scope daily --stdout
pytest
```

| Command | Purpose |
|---------|---------|
| `python -m alloccontext ingest` | Pull configured sources → SQLite |
| `python -m alloccontext rollup --scope daily --stdout` | ContextBundle JSON (facts) |
| `python -m alloccontext status` | Per-source ingest ages, snapshots, MCP `/health` |
| `alloc-context mcp` | MCP server (stdio or HTTP) |

Optional HTTP MCP + x402 on **your** host: [mcp-http.md](docs/mcp-http.md).

## Hosted MCP (retired)

AllocContext is **self-host only**. We no longer operate `mcp.alloc-context.com`.
Legacy bridge/hosted docs: [agent-integration.md](docs/agent-integration.md).

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/cursor-mcp.md](docs/cursor-mcp.md) | **Start here** — Cursor stdio MCP |
| [docs/self-hosting.md](docs/self-hosting.md) | Local ingest + MCP |
| [docs/user-config.md](docs/user-config.md) | Bridge `user.yaml` (legacy, optional) |
| [docs/deterministic-context-mcp-pattern.md](docs/deterministic-context-mcp-pattern.md) | Ingest → rollup → MCP pattern |
| [docs/mcp.md](docs/mcp.md) | MCP tools |
| [docs/examples.md](docs/examples.md) | Sample tool JSON (redacted) |
| [docs/context-bundle.md](docs/context-bundle.md) | ContextBundle schema |
| [docs/USE.md](docs/USE.md) | License and use policy |
| [docs/local-dev.md](docs/local-dev.md) | Local internal MCP + dev ingest |
| [docs/docker-self-host.md](docs/docker-self-host.md) | Docker Compose self-host |
| [docs/distribution.md](docs/distribution.md) | PyPI and MCP Registry |
| [docs/publishing.md](docs/publishing.md) | Release workflow |
| [docs/agent-integration.md](docs/agent-integration.md) | Legacy hosted HTTP + x402 (retired) |

## Contributing

GitHub Issues are welcome for bugs, schema feedback, and MCP API suggestions.
Unsolicited pull requests are not expected — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT License](LICENSE). Self-host via PyPI. See [docs/USE.md](docs/USE.md).
