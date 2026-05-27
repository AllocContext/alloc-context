# MCP + x402 roadmap

AllocContext is becoming an **agent-native allocation context API**: structured
facts and rebalance math, discoverable via the x402 Bazaar, paid per call.

Today, email briefs and LLM synthesis live in the same repo as the facts
engine. **Phase E** extracts them into a separate operator package. Until
then, the operator path (cron + email) and the product path (MCP) share core
rollup code but serve different audiences.

## Product split

| Surface | Audience | Status |
|---------|----------|--------|
| **MCP server `alloc-context`** | Agents + developers | Shipped (stdio, Tier 1) |
| **x402 paywall** | Agent wallets | Shipped (Phase B) |
| **Bazaar listing** | Discovery | Phase C |
| **Multi-exchange + BYOK portfolio** | Agents with exchange keys | Phase D |
| CLI + systemd ingest | Operator self-host | Shipped (moves to core package) |
| Email briefs + band alerts + LLM synthesis | Operator (you) | Shipped → **Phase E extract** |

Core MCP is **facts only, no LLM**. Agents narrate JSON with their host model;
server-side synthesis is not additive to the paid API.

## MCP tools

### Tier 1 — no user keys (public context + math)

| Tool | Input | Output |
|------|-------|--------|
| `get_market_context` | `scope` (daily/weekly) | ContextBundle subset: sentiment, macro, ETF, breadth, `as_of`, `age_seconds` |
| `get_rebalance_plan` | `allocation_pct`, `target_pct`, `nav_usd` | USD deltas + exchange-style move lines |
| `check_allocation_band` | `allocation_pct`, `target_pct`, `band` | `hint`, drift, `outside_band` |

Shipped on stdio (Phase A). Cached context comes from operator ingest DB on
self-host; hosted Phase B serves the same facts from server-side cache.

### Tier 2 — BYOK live portfolio (Phase D)

| Tool | Input | Output |
|------|-------|--------|
| `get_portfolio_state` | `exchange`, read-only credentials in request | Portfolio slice of ContextBundle: NAV, allocation, drift |

Credentials are **pass-through only** — never stored server-side. Initial
exchanges: **Kraken** (existing ingest) and **Coinbase** (Advanced Trade
read-only). Unified response shape regardless of exchange.

## x402 + Bazaar

1. HTTP/MCP middleware returns `402 Payment Required` with USDC price on Base.
2. Register routes with **Bazaar extension** metadata (semantic description for
   agent search).
3. List on CDP facilitator / Agent.market.

Target pricing (initial): **$0.01–0.05/call** Tier 1; **$0.05–0.10** Tier 2
live portfolio (per exchange).

Bazaar title:

> AllocContext — BTC/ETH allocation drift, rebalance moves & market context

## Implementation phases

### Phase A — MCP skeleton (no payment) ✅

- [x] `alloccontext/mcp/` module — MCP server over stdio
- [x] Wire Tier 1 tools to existing rollup + `rebalance.py`
- [x] JSON schemas + `as_of` / `age_seconds` on every response
- [x] Local Cursor config for dogfooding

### Phase B — x402 gate

- [x] HTTP / streamable transport for MCP (alongside stdio)
- [x] x402 middleware on paid routes (`alloc-context mcp --transport http --x402`)
- [x] CDP facilitator + seller wallet via env (`X402_*`, `CDP_API_KEY_*`)
- [x] Staleness tiers: `freshness=cached|live` on `get_market_context`

### Phase C — Discovery

- [ ] Bazaar metadata on all paid routes
- [ ] Listing copy optimized for agent semantic search
- [ ] Dogfood via `x402-discovery-mcp` in Cursor

### Phase D — Personalization & multi-exchange

**Exchange & portfolio**

- [ ] Exchange abstraction in ingest + rollup (`kraken`, `coinbase` first)
- [ ] Coinbase Advanced Trade read-only: balances, spot positions, USD NAV
- [ ] MCP `exchange` parameter on portfolio and rebalance tools
- [ ] `get_portfolio_state` Tier 2 BYOK (credentials in request, never stored)
- [ ] Exchange-specific move-line wording (Kraken vs Coinbase order semantics)

**Asset & target configuration**

- [ ] Per-request `assets` filter (default `BTC`, `ETH`; allocation universe
      remains BTC/ETH/CASH until expanded deliberately)
- [ ] Per-request `target_pct` / `band` (already on math tools; document as
      first-class MCP contract)
- [ ] Optional server defaults via config for operator self-host

**Richer deterministic fields (no LLM)**

- [ ] Structured regime / hint fields in ContextBundle where agents benefit
- [ ] Explicit delta blocks for `prior_as_of` comparisons

**Suggested PR slices**

1. `exchange` config schema + Kraken refactor (no new exchange yet)
2. Coinbase ingest + portfolio adapter
3. MCP Tier 2 BYOK + `exchange` param

### Phase E — Operator package extraction

Split **human email + LLM synthesis** from the public facts engine.

**Moves to `alloc-context-operator` (depends on core)**

- [ ] `brief/` — daily/weekly orchestration
- [ ] `synthesize/` — LLM prompts, OpenAI, allocation advice prose
- [ ] `deliver/` — Resend email, markdown render, alert delivery
- [ ] `review/` — monthly forward-watch review
- [ ] `predictions/` — forward watches extracted from brief prose (if kept)
- [ ] CLI: `brief`, `review`, `alerts --email`
- [ ] systemd brief/alert timers; optional meta-package for VPS

**Stays in core (`alloc-context`)**

- [ ] `ingest/`, `store/`, `rollup/`, `mcp/`, exchange adapters
- [ ] Band **evaluation** math (alerts call core; delivery lives in operator)
- [ ] Break `ingest/runner` → email alert coupling (ingest refreshes data only)

**Install shape**

```text
pip install alloc-context[mcp]           # public product
pip install alloc-context-operator     # private/ops; depends on alloc-context
```

### Final — public polish & orphan reset

After Phases B–E:

- [ ] Doc hygiene: drop migration scratch, slim README to product surface
- [ ] Orphan reset → single clean public root commit
- [ ] Flip repo public (if not already)

## Non-goals

**Core MCP (Phases B–D)**

- LLM on any paid MCP path (agents narrate Tier 1/2 JSON themselves)
- Holding user exchange secrets server-side
- BYOLLM / server-side narrative tools
- More than BTC/ETH/CASH in allocation math unless explicitly expanded

**Explicitly in scope for Phase D**

- Multi-exchange **live** portfolio via BYOK (Kraken + Coinbase first)

**Operator package (Phase E) — not public product**

- LLM synthesis and email are for the VPS operator path only
- Resend + OpenAI deps move to operator optional extras

**Still out of scope (for now)**

- Automated trade execution
- Server-hosted custody or Agentic Wallets integration
- Exotic asset universes (altcoins, perps, staking beyond spot cash/crypto split)
- Every exchange — prove Kraken + Coinbase adapter pattern first

## Repo layout (evolving)

**Core (public after Phase E)**

```text
alloccontext/
  mcp/
    server.py
    handlers.py
  ingest/
    kraken_*.py
    coinbase_*.py      # Phase D
    exchange/          # Phase D
  rollup/
    portfolio.py
    band.py
    rebalance.py
```

**Operator (Phase E — separate package or private repo)**

```text
alloccontext_operator/   # or alloc-context-operator/
  brief/
  synthesize/
  deliver/
  review/
  predictions/
```

See [context-bundle.md](context-bundle.md) for the facts schema MCP tools expose.
