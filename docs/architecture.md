# Architecture

## Purpose

**AllocContext** — deterministic market facts, portfolio rollups, and MCP tools
for agents. Exchange APIs and third-party feeds are **data sources only** — no
order placement, no gate authority, no bot shadow modes.

**Integration surface:** MCP tools only (`get_context_bundle`,
`get_market_context`, `get_portfolio_state`, `get_rebalance_plan`,
`check_allocation_band`). Email briefs, band alerts, and LLM synthesis belong
in a separate operator stack that calls MCP — see
[alloc-context-operator](https://github.com/negillett/alloc-context-operator).

Agent-facing MCP + x402: [mcp.md](mcp.md).

## Pipeline

```text
┌──────────────────────────────────────────────────────────────────┐
│                         alloc-context                            │
├──────────────────────────────────────────────────────────────────┤
│  ingest/          Scheduled pulls → normalized rows               │
│  store/           SQLite append-only snapshots                    │
│  rollup/          ContextBundle (deterministic, reproducible)     │
│  mcp/             Agent tools + optional x402 HTTP                  │
└──────────────────────────────────────────────────────────────────┘
```

## Trust boundaries

| Layer | LLM? | Places orders? | Sends email? |
|-------|------|----------------|--------------|
| Ingest | No | No | No |
| Rollup | No | No | No |
| MCP | No | No | No |

## Data horizon

One quarterly window (`horizon.days: 90` by default) for everything persisted:
market bars, sentiment history, portfolio snapshots, and rollup snapshots in
`context_snapshots`. Rollups should not assume data older than this unless
explicitly archived off-system.

## ContextBundle

JSON document at a point in time. See [context-bundle.md](context-bundle.md).

Sections:

- `portfolio` — NAV, allocation, drift vs target, P&L windows
- `market` — BTC/ETH OHLC-derived signals
- `sentiment` — Kalshi cluster, F&G, optional breadth
- `macro` — calendar events past 24h / next 7d, ETF flows when enabled
- `delta` — changes since prior saved snapshot

Expose via MCP `get_context_bundle` or CLI `rollup --stdout`.

## Optional self-hosting

Linux + systemd timer for scheduled ingest (feeds the MCP cache) is documented
in [self-hosting.md](self-hosting.md). Operator email/alerts are deployed from
the operator repository, not this one.

## Non-goals

- Automated trade execution
- Holding user exchange secrets on a shared MCP server (BYOK in request only)
- Email, LLM synthesis, or alert delivery in this repo
- Backtest / replay engines
- Multi-user SaaS
