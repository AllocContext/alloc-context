# MCP product

AllocContext is an **agent-native portfolio context API**: discover holdings,
market, sentiment, macro, and regime; optional allocation analysis —
exposed as MCP tools, with a paid HTTP endpoint via x402 on Base.

This repo is **facts only** — agents narrate JSON with their own model. Email,
LLM synthesis, and alert delivery are out of scope here.

## Surfaces

| Surface | Audience |
|---------|----------|
| **MCP (stdio bridge)** | Cursor and local agents (default) |
| **MCP (stdio self-host)** | Local ingest dev and operator-style |
| **MCP (HTTP + x402)** | Agents and wallets on the public internet |
| **Bazaar / discovery** | Agent search via CDP and `/.well-known/x402.json` |
| **CLI + ingest** | Self-hosted cache for MCP context tools |

## Tools

### Cached context and math (no user keys)

Shared optional args on context tools:

| Arg | Tools | Default | Purpose |
|-----|-------|---------|---------|
| `assets` | `get_context_bundle`, `get_market_context`, `get_context_at`, `get_context_delta` | `["BTC","ETH"]` | Filter market and ETF fields; unknown symbols (e.g. HYPE) are omitted and listed in `assets_omitted`. **Bridge:** when omitted and exchange keys are set, symbols are derived from local portfolio holdings (symbols only sent upstream — no qty/NAV). |
| `target_pct` | `get_context_bundle` | omitted | Opt-in: attach `allocation_analysis` drift math |
| `band` | `get_context_bundle`, `get_rebalance_plan` | omitted / none | Drift band width when used with `target_pct` |

Math tools require explicit `target_pct` and `band`. On `get_context_bundle`,
pass `target_pct` (and optional `band`) to attach `allocation_analysis`.

| Tool | Input | Output |
|------|-------|--------|
| `get_market_context` | `scope`, optional `freshness`, optional `assets` | Sentiment, macro, ETF, breadth, `market`, `as_of`, `age_seconds` |
| `get_context_bundle` | `scope`, optional `freshness`, optional `assets`, optional `target_pct`, optional `band` | Full ContextBundle; optional `allocation_analysis` when targets supplied |
| `get_context_at` | `as_of`, optional `scope`, `match`, optional `assets` | Saved snapshot from ingest history |
| `get_context_delta` | `prior_as_of`, optional `scope`, optional `current_as_of`, optional `assets` | `notable_shifts` between two bundles |
| `get_rebalance_plan` | `allocation_pct`, `target_pct`, `nav_usd`, optional `band` | USD deltas, move lines, optional `band_check` |
| `check_allocation_band` | `allocation_pct`, `target_pct`, `band` | Drift, `outside_band`, `hint` |
| `check_allocation_bands` | `allocation_pct`, `scenarios[]` | Batch band checks for multiple targets |

On a self-hosted install, `freshness=cached` reads the ingest SQLite DB.
Hosted endpoints serve the host ingested cache unless the client requests
`freshness=live` (requires API keys on the host).

### Response staleness

`get_context_bundle` and `get_market_context` carry two staleness signals:

| Field | Meaning |
|-------|---------|
| `as_of` / `age_seconds` | When the **response** was generated (≈ now for cached reads) |
| `data_as_of` / `data_age_seconds` | Oldest **underlying fact** in the payload (portfolio snapshot, sentiment, breadth) — use this to judge data freshness |

`data_*` is omitted only when no constituent timestamp is present. A
`freshness=live` request whose ingest does not succeed fails closed: the
response is `{ "available": false, "reason": "live_ingest_failed", ... }`
rather than a stale bundle presented as live. Optional-source-only failures
keep ingest `ok` and still return a bundle.

### Live portfolio (credentials in request)

| Tool | Input | Output |
|------|-------|--------|
| `get_portfolio_state` | `exchange`, read-only credentials, optional `target_pct`, optional `band` | NAV, `holdings[]`, optional `allocation_analysis` |

Credentials are **pass-through only** — never stored server-side. Supported
exchanges: **Kraken** and **Coinbase** Advanced Trade (read-only). Disable
Coinbase in `ingest.sources` and `exchanges.coinbase.enabled` when unused.

## MCP resources

| URI | Content |
|-----|---------|
| `context-bundle://schema/v2` | ContextBundle JSON Schema (portfolio-first) |
| `context-bundle://schema/v1` | Legacy schema (pre-holdings) |
| `alloc-context://tools/rebalance-hints` | Meaning of `rebalance_hint` codes |

## Ingest reliability

Optional ingest APIs (`fred`, `finnhub`, `fmp`, `coingecko`, `coinmarketcap`,
`sosovalue` by default) may fail without failing the hourly ingest run. Finnhub,
FMP, and SoSoValue failures are tracked under those names in `source_health` even
when the parent source is `macro_calendar` or `etf_flows`. Check `partial`,
`optional_errors`, and `fatal_errors` in ingest JSON output; `python -m
alloccontext status` includes `source_health` per source.

## x402 pricing

Hosted MCP uses **per-call x402 exact on Base mainnet**. Payer chooses a
USD-pegged stable (default **USDC, EURC**; bridge to Base first):

| Call type | Default price | Env |
|-----------|---------------|-----|
| Cached context and math tools | **$0.02** | `X402_PRICE_MCP` |
| Live portfolio or `freshness=live` | **$0.05** | `X402_PRICE_MCP_HEAVY` |

`X402_ACCEPTED_STABLES` controls which stables appear in 402 `accepts`.
Setup: [mcp-http.md](mcp-http.md). Discovery: [mcp-discovery.md](mcp-discovery.md).
Agent integration: [agent-integration.md](agent-integration.md). Samples:
[examples.md](examples.md).

Tool JSON contracts are validated in `tests/test_mcp_contracts.py` via
`alloccontext.mcp.contracts` (required keys per tool).

Bazaar listing title:

> AllocContext — portfolio-aware crypto context for agents (MCP + x402)

## Packages

```text
pip install "alloc-context[mcp]"      # stdio MCP
pip install "alloc-context[hosted]"   # HTTP + x402
```

## Non-goals

- LLM on any paid MCP path
- Storing user exchange secrets on a shared server (credentials in request only)
- Automated trade execution
- Asset universes beyond BTC / ETH / CASH unless explicitly expanded

See [context-bundle.md](context-bundle.md) for the facts schema.
