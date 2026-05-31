# AllocContext

[![smithery badge](https://smithery.ai/badge/@negillett/alloc-context)](https://smithery.ai/server/@negillett/alloc-context)
[![Glama MCP server](https://glama.ai/mcp/servers/negillett/alloc-context/badges/score.svg)](https://glama.ai/mcp/servers/negillett/alloc-context)

mcp-name: io.github.negillett/alloc-context

**Portfolio-aware crypto context for agents** — discover holdings, market,
sentiment, macro, and regime; optional allocation analysis. Deterministic
JSON over MCP with x402 pay-per-call on Base.

> **Privacy:** nothing stored · one-time read-only · pass-through only — your
> keys and portfolio never persist on our servers. See [USE.md](docs/USE.md).

## Quick start (Cursor)

**1. Install**

```bash
pip install "alloc-context[mcp,hosted]"
# From source: pip install -e ".[mcp,hosted]"
```

**2. User config**

Copy [config/user.example.yaml](config/user.example.yaml) to
`~/.config/alloc-context/user.yaml`. Add read-only exchange keys for portfolio
discovery (optional) and an x402 payer for hosted market context. See
[user-config.md](docs/user-config.md).

**3. MCP config**

Add to your Cursor `mcp.json` (or project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "alloc-context": {
      "command": "alloc-context",
      "args": [
        "mcp",
        "--user-config",
        "/Users/you/.config/alloc-context/user.yaml"
      ]
    }
  }
}
```

Use an absolute path for `--user-config`. Example:
[cursor-mcp-bridge.example.json](docs/cursor-mcp-bridge.example.json).

**4. Ask your agent**

Call `get_context_bundle` for a full snapshot (holdings when keys are set,
market/sentiment/macro via hosted upstream). Pure math tools
(`check_allocation_band`, `get_rebalance_plan`) work without exchange keys.

Full setup guide: [cursor-mcp.md](docs/cursor-mcp.md). Sample responses:
[examples.md](docs/examples.md).

Not financial advice.

## Hosted MCP

| | |
|--|--|
| **URL** | `https://mcp.alloc-context.com/mcp` |
| **Discovery** | [llms.txt](https://mcp.alloc-context.com/llms.txt), [x402 manifest](https://mcp.alloc-context.com/.well-known/x402.json) |
| **Pricing** | **$0.02** cached context/math · **$0.05** live ingest or portfolio |
| **Payment** | x402 on Base — USDC or EURC |

Agents and wallets connect directly to the hosted endpoint — see
[agent-integration.md](docs/agent-integration.md). The Cursor bridge above
combines local portfolio reads with this upstream for market context.

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
| `get_portfolio_state` | Live NAV and holdings from Kraken or Coinbase |

Market context is **holdings-scoped**: band assets (BTC/ETH) use OHLC bars; alt
holdings (e.g. HYPE) use quote snapshots when cached. The bridge auto-scopes
`assets` from your portfolio (symbols only upstream). See
[context-bundle.md#market-coverage](docs/context-bundle.md#market-coverage).

See [mcp.md](docs/mcp.md) for arguments, pricing, and resources.

## Self-host and development

Run ingest and MCP entirely on your machine — no x402 upstream required.
See [self-hosting.md](docs/self-hosting.md) (`self_host: true` in user config)
or [local-dev.md](docs/local-dev.md) for the dev stack.

```bash
git clone git@github.com:negillett/alloc-context.git
cd alloc-context
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
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

HTTP MCP + x402: [mcp-http.md](docs/mcp-http.md). CLI entry point:
`alloc-context` (same as `python -m alloccontext`).

## Documentation

| Document | Purpose |
|----------|---------|
| [docs/cursor-mcp.md](docs/cursor-mcp.md) | Cursor stdio MCP (bridge default) |
| [docs/user-config.md](docs/user-config.md) | Bridge `user.yaml` reference |
| [docs/mcp.md](docs/mcp.md) | MCP tools and x402 |
| [docs/agent-integration.md](docs/agent-integration.md) | Paid HTTP MCP + Bazaar for agents |
| [docs/examples.md](docs/examples.md) | Sample tool JSON (redacted) |
| [docs/context-bundle.md](docs/context-bundle.md) | ContextBundle schema |
| [docs/USE.md](docs/USE.md) | Self-host vs hosted MCP (plain language) |
| [docs/mcp-http.md](docs/mcp-http.md) | HTTP MCP + x402 setup |
| [docs/mcp-discovery.md](docs/mcp-discovery.md) | Bazaar and agent discovery |
| [docs/self-hosting.md](docs/self-hosting.md) | Optional Linux/systemd ingest + MCP |
| [docs/local-dev.md](docs/local-dev.md) | Local internal MCP + dev ingest |
| [docs/architecture.md](docs/architecture.md) | Pipeline and trust boundaries |
| [docs/data-sources.md](docs/data-sources.md) | Ingest sources |
| [docs/distribution.md](docs/distribution.md) | GitHub, PyPI, MCP Registry, directories |
| [docs/publishing.md](docs/publishing.md) | Release workflow and version bumps |
| [docs/security-ci.md](docs/security-ci.md) | CI coverage, Bandit, and pip-audit gates |

## Contributing

GitHub Issues are welcome for bugs, schema feedback, and MCP API suggestions.
Unsolicited pull requests are not expected — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Elastic License 2.0](LICENSE) — source-available, self-host friendly. See
[docs/USE.md](docs/USE.md) for plain-language allowed uses.

**Official hosted MCP:** `https://mcp.alloc-context.com/mcp`
