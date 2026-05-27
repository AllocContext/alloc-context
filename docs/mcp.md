# MCP product

AllocContext is an **agent-native allocation context API**: deterministic
BTC/ETH facts, rebalance math, and optional live portfolio reads — exposed as
MCP tools, with a paid HTTP endpoint via x402 on Base.

Email briefs and LLM synthesis live in
[alloc-context-operator](https://github.com/negillett/alloc-context-operator).
This repo is **facts only** — agents narrate JSON with their own model.

## Surfaces

| Surface | Audience |
|---------|----------|
| **MCP (stdio)** | Local development and Cursor |
| **MCP (HTTP + x402)** | Agents and wallets on the public internet |
| **Bazaar / discovery** | Agent search via CDP and `/.well-known/x402.json` |
| **CLI + ingest** | Self-hosted cache for MCP Tier 1 |

## Tools

### Tier 1 — cached context and math (no user keys)

| Tool | Input | Output |
|------|-------|--------|
| `get_market_context` | `scope`, optional `freshness` | Sentiment, macro, ETF, breadth, `as_of`, `age_seconds` |
| `get_context_bundle` | `scope`, optional `freshness` | Full ContextBundle |
| `get_rebalance_plan` | `allocation_pct`, `target_pct`, `nav_usd` | USD deltas and move lines |
| `check_allocation_band` | `allocation_pct`, `target_pct`, `band` | Drift, `outside_band`, `hint` |

On a self-hosted install, `freshness=cached` reads the ingest SQLite DB.
Hosted endpoints serve the operator's ingested cache unless the client requests
`freshness=live` (requires API keys on the host).

### Tier 2 — BYOK live portfolio

| Tool | Input | Output |
|------|-------|--------|
| `get_portfolio_state` | `exchange`, read-only credentials in request | NAV, allocation, drift |

Credentials are **pass-through only** — never stored server-side. Supported
exchanges: **Kraken** and **Coinbase** Advanced Trade (read-only).

## x402 pricing

Default hosted price: **$0.02 USDC per call** on Base mainnet (`X402_PRICE_MCP`).

Typical ranges: **$0.01–0.05** Tier 1; **$0.05–0.10** Tier 2 live portfolio.

Setup: [mcp-http.md](mcp-http.md). Discovery: [mcp-discovery.md](mcp-discovery.md).

Bazaar listing title:

> AllocContext — BTC/ETH allocation drift, rebalance moves & market context

## Packages

```text
pip install "alloc-context[mcp]"      # stdio MCP
pip install "alloc-context[hosted]"   # HTTP + x402
pip install alloc-context-operator    # email briefs (separate repo)
```

## Non-goals

- LLM on any paid MCP path
- Storing user exchange secrets on a shared server (BYOK in request only)
- Automated trade execution
- Asset universes beyond BTC / ETH / CASH unless explicitly expanded

See [context-bundle.md](context-bundle.md) for the facts schema.
