# MCP product

AllocContext is an **agent-native portfolio context API**: discover holdings,
market, sentiment, macro, and regime; optional allocation analysis — exposed as
MCP tools over **self-host** stdio or optional HTTP on your infrastructure.

This repo is **facts only** — agents narrate JSON with their own model. Email,
LLM synthesis, and alert delivery are out of scope here.

## Surfaces

| Surface | Audience |
|---------|----------|
| **MCP (stdio + `--config`)** | Cursor and local agents (**default**) |
| **MCP (HTTP, loopback)** | `./scripts/local-up.sh`, Docker, [local-dev.md](local-dev.md) |
| **MCP (HTTP + x402)** | Optional paid gate on **your** public URL — [mcp-http.md](mcp-http.md) |
| **CLI + ingest** | SQLite cache for MCP context tools |

AllocContext does **not** operate `mcp.alloc-context.com`. Quickstart:
[cursor-mcp.md](cursor-mcp.md), [agent-onramp.md](agent-onramp.md).

## Tools

### Cached context and math (no user keys)

Shared optional args on context tools:

| Arg | Tools | Default | Purpose |
|-----|-------|---------|---------|
| `assets` | `get_context_bundle`, `get_market_context`, `get_context_at`, `get_context_delta` | `["BTC","ETH"]` | Filter market and ETF fields; unknown symbols (e.g. HYPE) are omitted and listed in `assets_omitted`. Pass symbols explicitly for alts. |
| `target_pct` | `get_context_bundle` | omitted | Opt-in: attach `allocation_analysis` drift math |
| `band` | `get_context_bundle`, `get_rebalance_plan` | omitted / none | Drift band width when used with `target_pct` |
| `theses` | `get_context_bundle` | omitted | Opt-in: attach `expectation_review` (pass-through beliefs; nothing stored) |

Math tools require explicit `target_pct` and `band`. On `get_context_bundle`,
pass `target_pct` (and optional `band`) to attach `allocation_analysis`.
Pass `theses[]` to score local thesis claims deterministically — see
[Privacy: theses](#privacy-theses) below.

| Tool | Input | Output |
|------|-------|--------|
| `get_market_context` | `scope`, optional `freshness`, optional `assets` | Sentiment, macro, ETF, breadth, `market`, `as_of`, `age_seconds` |
| `get_context_bundle` | `scope`, optional `freshness`, optional `assets`, optional `target_pct`, optional `band`, optional `theses[]` | Full ContextBundle; optional `allocation_analysis` when targets supplied; optional `expectation_review` when `theses[]` supplied |
| `get_expectation_review` | `theses[]`, optional `scope`, optional `freshness`, optional `target_pct`, optional `band`, optional `expectation_replay` | Thesis scoring only (same fields as `expectation_review` block) |
| `get_context_at` | `as_of`, optional `scope`, `match`, optional `assets` | Saved snapshot from ingest history |
| `get_context_delta` | `prior_as_of`, optional `scope`, optional `current_as_of`, optional `assets` | `notable_shifts` between two bundles |
| `get_rebalance_plan` | `allocation_pct`, `target_pct`, `nav_usd`, optional `band` | USD deltas, move lines, optional `band_check` |
| `check_allocation_band` | `allocation_pct`, `target_pct`, `band` | Drift, `outside_band`, `hint` |
| `check_allocation_bands` | `allocation_pct`, `scenarios[]` | Batch band checks for multiple targets |

On a self-hosted install, `freshness=cached` reads the ingest SQLite DB.
`freshness=live` triggers targeted alt quote refresh for requested symbols
(requires ingest keys; heavier work — see [mcp-http.md](mcp-http.md) if you
enable x402 pricing on HTTP).

### Market coverage

| Class | Symbols | Ingest | Response |
|-------|---------|--------|----------|
| **Band** | BTC, ETH | OHLC bars + ETF flows | `market.assets.btc`, `market.assets.eth` with bar-based change |
| **Alt holdings** | e.g. HYPE | Quote snapshots (CMC/CG/exchange) | `market.assets.{symbol}` with mark + 24h change |
| **Stables** | USD, USDC, … | Portfolio only | Not in market `assets` filter |
| **Global** | Market-wide | Sentiment, macro, breadth | `sentiment`, `macro`; ETF BTC/ETH only |

Details: [context-bundle.md#market-coverage](context-bundle.md#market-coverage).
Missing symbols → `assets_omitted[]`.

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

### Live portfolio (CEX keys or wallet address in request)

| Tool | Input | Output |
|------|-------|--------|
| `get_portfolio_state` | `exchange`, CEX read-only credentials **or** `wallet_address`, optional `target_pct`, optional `band` | NAV, `holdings[]`, optional `allocation_analysis` |

CEX credentials are **pass-through only** — never stored server-side. Supported
sources: **Kraken**, **Coinbase** Advanced Trade (read-only), and **wallet**
(public EVM address — keyless for the caller; host needs `ALCHEMY_API_KEY` by default).
See [data-sources.md](data-sources.md#on-chain-wallet-evm-keyless).

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

## Optional x402 pricing (self-operated HTTP)

When you run HTTP MCP with `--x402` on **your** infrastructure, default tiers
are per-call x402 exact on Base mainnet. Payer chooses a USD-pegged stable
(default **USDC, EURC**):

| Call type | Default price | Env |
|-----------|---------------|-----|
| Cached context and math tools | **$0.02** | `X402_PRICE_MCP` |
| Live portfolio or `freshness=live` | **$0.05** | `X402_PRICE_MCP_HEAVY` |

`X402_ACCEPTED_STABLES` controls which stables appear in 402 `accepts`.
Setup: [mcp-http.md](mcp-http.md). Discovery: [mcp-discovery.md](mcp-discovery.md).
Samples: [examples.md](examples.md).

Tool JSON contracts are validated in `tests/test_mcp_contracts.py` via
`alloccontext.mcp.contracts` (required keys per tool).

## Packages

```text
pip install "alloc-context[mcp]"      # stdio MCP (default)
pip install "alloc-context[hosted]"   # HTTP + optional x402 on your host
```

## Privacy: theses

Optional `theses[]` on `get_context_bundle` enables deterministic
`expectation_review` scoring ([context-bundle.md](context-bundle.md)). Same
privacy model as CEX keys and wallet addresses:

| Pillar | Behavior |
|--------|----------|
| **Nothing stored** | Thesis payloads and scored output are **not** written to SQLite logs or long-lived cache beyond the request. |
| **One-time read-only** | Used only for the request lifecycle — score claims vs saved market snapshots, return JSON, discard. |
| **Pass-through only** | Beliefs live in **your** agent or config; the server never owns or edits them. |

Pass `theses[]` on the tool call (or configure entries in legacy bridge
`user.yaml` — [user-config.md](user-config.md)). Baselines resolve from ingest
snapshot history at each thesis `recorded_at`.

See also [USE.md](USE.md).

## Non-goals

- LLM on any paid MCP path
- Storing user exchange secrets on a shared server (credentials in request only)
- Automated trade execution
- Per-alt ETF flow ingest (ETF remains BTC/ETH-centric)
- New exchanges beyond Kraken and Coinbase

See [context-bundle.md](context-bundle.md) for the facts schema.
