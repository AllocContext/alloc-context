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
| **CLI + ingest** | Self-hosted cache for MCP context tools |

## Tools

### Cached context and math (no user keys)

Shared optional args on context tools:

| Arg | Tools | Default | Purpose |
|-----|-------|---------|---------|
| `assets` | `get_context_bundle`, `get_market_context` | `["BTC","ETH"]` | Filter market and ETF fields |
| `target_pct` | `get_context_bundle` | server config | Override target weights for drift math |
| `band` | `get_context_bundle`, `get_rebalance_plan` | server config / none | Drift band width (e.g. `0.15`) |

Math tools require explicit `target_pct` and `band` (or use `get_context_bundle`
for cached portfolio drift with optional overrides).

| Tool | Input | Output |
|------|-------|--------|
| `get_market_context` | `scope`, optional `freshness`, optional `assets` | Sentiment, macro, ETF, breadth, `market`, `as_of`, `age_seconds` |
| `get_context_bundle` | `scope`, optional `freshness`, optional `assets`, optional `target_pct`, optional `band` | Full ContextBundle including `regime` hints |
| `get_rebalance_plan` | `allocation_pct`, `target_pct`, `nav_usd`, optional `band` | USD deltas, move lines, optional `band_check` |
| `check_allocation_band` | `allocation_pct`, `target_pct`, `band` | Drift, `outside_band`, `hint` |

On a self-hosted install, `freshness=cached` reads the ingest SQLite DB.
Hosted endpoints serve the host ingested cache unless the client requests
`freshness=live` (requires API keys on the host).

### Live portfolio (credentials in request)

| Tool | Input | Output |
|------|-------|--------|
| `get_portfolio_state` | `exchange`, read-only credentials, optional `target_pct`, optional `band` | NAV, allocation, drift |

Credentials are **pass-through only** — never stored server-side. Supported
exchanges: **Kraken** and **Coinbase** Advanced Trade (read-only).

## x402 pricing

Hosted MCP uses **per-call USDC on Base mainnet**:

| Call type | Default price | Env |
|-----------|---------------|-----|
| Cached context and math tools | **$0.02** | `X402_PRICE_MCP` |
| Live portfolio or `freshness=live` | **$0.05** | `X402_PRICE_MCP_HEAVY` |

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
- Storing user exchange secrets on a shared server (credentials in request only)
- Automated trade execution
- Asset universes beyond BTC / ETH / CASH unless explicitly expanded

See [context-bundle.md](context-bundle.md) for the facts schema.
