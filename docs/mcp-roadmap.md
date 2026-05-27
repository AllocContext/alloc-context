# MCP + x402 roadmap

AllocContext is becoming an **agent-native allocation context API**: structured
facts and rebalance math, discoverable via the x402 Bazaar, paid per call.

Email briefs and optional self-host ingest remain an operator path. MCP is the
product path.

## Product split

| Surface | Audience | Status |
|---------|----------|--------|
| CLI + systemd ingest | Operator self-host | Shipped |
| Email briefs + band alerts | Operator self-host | Shipped |
| **MCP server `alloc-context`** | Agents + developers | Planned |
| **x402 paywall** | Agent wallets | Planned |
| **Bazaar listing** | Discovery | Planned |

## MCP tools (v1)

Tier 1 — **no exchange keys** (public context + math):

| Tool | Input | Output |
|------|-------|--------|
| `get_market_context` | `scope` (daily/weekly) | ContextBundle subset: sentiment, macro, ETF, breadth, `as_of`, `age_seconds` |
| `get_rebalance_plan` | `allocation_pct`, `target_pct`, `nav_usd` | USD deltas + Kraken-style move lines |
| `check_allocation_band` | `allocation_pct`, `target_pct`, `band` | `hint`, drift, `outside_band` |

Tier 2 — **BYOK Kraken read-only** (later):

| Tool | Input | Output |
|------|-------|--------|
| `get_portfolio_state` | read-only API key in request or pre-registered token | Portfolio slice of ContextBundle |

Default paid path: **facts only, no LLM**. Optional `with_narrative=true` at higher
price if demand appears.

## x402 + Bazaar

1. HTTP/MCP middleware returns `402 Payment Required` with USDC price on Base.
2. Register routes with **Bazaar extension** metadata (semantic description for
   agent search).
3. List on CDP facilitator / Agent.market.

Target pricing (initial): **$0.01–0.05/call** Tier 1; **$0.05–0.10** Tier 2 live
portfolio.

Bazaar title:

> AllocContext — BTC/ETH allocation drift, rebalance moves & market context

## Implementation phases

### Phase A — MCP skeleton (no payment)

- [ ] `alloccontext/mcp/` module — MCP server over stdio or HTTP
- [ ] Wire Tier 1 tools to existing rollup + `rebalance.py`
- [ ] JSON schemas + `as_of` / `age_seconds` on every response
- [ ] Local Cursor config for dogfooding

### Phase B — x402 gate

- [ ] `@x402` middleware on HTTP transport
- [ ] CDP facilitator + seller wallet
- [ ] Staleness tiers: cached vs on-demand refresh for paid `live` calls

### Phase C — Discovery

- [ ] Bazaar metadata on all paid routes
- [ ] Listing copy optimized for agent semantic search
- [ ] Dogfood via `x402-discovery-mcp` in Cursor

## Non-goals (v1 MCP)

- Holding user exchange secrets server-side
- LLM on every paid call
- Multi-exchange live portfolio
- More than BTC/ETH/CASH in allocation logic

## Repo layout (planned)

```text
alloccontext/
  mcp/
    server.py      # MCP tool definitions
    schemas.py     # tool input/output models
  rollup/          # existing ContextBundle builders
  ...
```

See [context-bundle.md](context-bundle.md) for the facts schema MCP tools expose.
