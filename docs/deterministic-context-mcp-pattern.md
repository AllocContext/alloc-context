# A deterministic, payable context MCP

A reusable architecture for agent tools that return **structured, reproducible
context** — not ad-hoc API scraping or LLM synthesis in the data path.

AllocContext implements this pattern for **portfolio-aware crypto context**.
The pipeline and trust boundaries generalize to other domains (inventory,
logistics, compliance snapshots) without changing the core idea.

**Privacy (AllocContext):** [USE.md](USE.md) — local data stays on hardware you
control; live reads are pass-through only.

> **Not financial advice.** Facts-only JSON; no trade execution.

---

## Problem

Agent frameworks work best with **typed, inspectable tool output**. Calling
market APIs from every agent turn is:

- **Non-reproducible** — upstream timestamps, rate limits, and partial failures
  change answers run-to-run.
- **Expensive** — duplicate fetches across tools and sessions.
- **Hard to test** — no stable fixture unless you build a cache layer anyway.

The pattern separates **data collection** (ingest + store) from **context
assembly** (deterministic rollup) from **delivery** (MCP tools), with an
optional **paywall** on HTTP when you operate a public endpoint.

---

## Pattern overview

```text
 Sources (APIs, files)          Agent callers
         │                              ▲
         ▼                              │
    ┌─────────┐    ┌──────────┐    ┌────┴────┐
    │ Ingest  │───▶│  Store   │───▶│ Rollup  │
    │ (pull)  │    │ append-  │    │ (pure)  │
    └─────────┘    │ only DB  │    └────┬────┘
                   └──────────┘         │
                                        ▼
                              ┌─────────────────┐
                              │ MCP tools       │
                              │ (fail-closed)   │
                              └────────┬────────┘
                                       │
                         optional x402 │ HTTP gate (your URL)
                                       ▼
                              Your MCP endpoint
```

| Stage | Role | LLM? | Must be deterministic? |
|-------|------|------|------------------------|
| **Ingest** | Pull configured sources on a schedule or on demand; normalize rows | No | Writes are idempotent per source run |
| **Store** | Append-only snapshots (SQLite or equivalent); bounded retention horizon | No | Same inputs → same stored facts |
| **Rollup** | Assemble a versioned context document at `as_of` | No | **Yes** — pure function of store state |
| **MCP** | Expose read-only tools; return JSON or setup objects when misconfigured | No | Tool output from rollup + pass-through reads |
| **Payment** (optional) | x402 on streamable HTTP you operate | No | Price tier follows work done (cached vs live) |

---

## Design principles

### 1. Facts only in the pipeline

Ingest and rollup produce **JSON facts** — prices, weights, calendar events,
regime labels derived from rules. No LLM summarization, no “takeaways” in the
core path. Agents (or a separate operator layer) interpret facts downstream.

### 2. Reproducible context bundles

Define a **ContextBundle** (or equivalent) schema: `as_of`, sections with
`available` flags, explicit omissions. Rollup reads the store and emits the
bundle. Same DB state + same rollup code → same bundle — useful for tests,
audits, and agent regression.

See [context-bundle.md](context-bundle.md) for AllocContext’s schema.

### 3. Fail-closed MCP

When config, credentials, or cache state is missing, tools return **structured
setup objects** (`available: false`, `reason`, steps) — not silent empty data or
hallucination-friendly prose. Agents can branch on `reason` and prompt the user
to fix config.

### 4. Pass-through secrets

Portfolio reads must not persist user exchange keys or portfolio payloads.
Credentials are **request-scoped** (tool args or `.env` on the host you
control). Market context comes from **your** ingest cache.

AllocContext policy: [USE.md](USE.md).

### 5. Optional pay-per-call (x402)

Monetization stays on the **HTTP transport** you operate, not in tool semantics:

- **Cached tier** — read pre-ingested snapshots (cheap).
- **Live tier** — trigger ingest or live portfolio work (defensible when
  replication is costly).

Agents pay per `tools/call` on Base via [x402](https://www.x402.org/) when you
enable the gate. Details: [mcp-http.md](mcp-http.md),
[mcp-discovery.md](mcp-discovery.md).

### 6. Self-host (default)

| Mode | Ingest | MCP | Payment |
|------|--------|-----|---------|
| **Self-host stdio** | On-demand or timer | `alloc-context mcp --config …` | None |
| **Self-host HTTP** | Same SQLite cache | Loopback or LAN HTTP | Optional x402 |

Self-host: [self-hosting.md](self-hosting.md), [docker-self-host.md](docker-self-host.md),
[cursor-mcp.md](cursor-mcp.md).

AllocContext **does not** operate a shared hosted MCP. Legacy bridge/hosted notes:
[agent-integration.md](agent-integration.md) (retired).

---

## AllocContext as the worked example

| Pattern piece | AllocContext implementation |
|---------------|----------------------------|
| Ingest | `alloccontext ingest` — Kraken, Coinbase, Kalshi, F&G, macro, ETF, etc. ([data-sources.md](data-sources.md)) |
| Store | SQLite append-only; 90-day horizon default ([architecture.md](architecture.md)) |
| Rollup | `ContextBundle` v2 — portfolio, market, sentiment, macro, regime, delta |
| MCP | stdio (default) or HTTP; tools in [mcp.md](mcp.md) |
| Discovery | MCP Registry (stdio package) — [distribution.md](distribution.md) |
| Optional payment | x402 on **your** HTTP URL — [mcp-http.md](mcp-http.md) |

**Integration paths for builders:**

- [agent-onramp.md](agent-onramp.md) — ~2 min to first ContextBundle
- [cursor-mcp.md](cursor-mcp.md) — Cursor stdio setup
- [distribution.md](distribution.md) — PyPI + MCP Registry

**Scope today:** crypto; portfolio from CEX read-only keys (Coinbase, Kraken)
or a public EVM wallet address ([data-sources.md](data-sources.md)).
Broader asset classes are demand-pulled only — no speculative expansion in the
reference implementation.

---

## When to use this pattern

**Good fit**

- Agents need **stable JSON context** (portfolio + environment, ticket + SLA
  state, account + market) refreshed on a known cadence.
- You want **one ingest** serving many agent sessions.
- You can draw a hard line: **facts in the MCP**, interpretation elsewhere.
- You may optionally monetize a **cache + live tier** on HTTP you operate (x402).

**Poor fit**

- Real-time streaming quotes with sub-second SLA (use a dedicated feed service).
- Consumer newsletters or digests (different product — see rejected consumer lane
  in project ADRs).
- Multi-tenant stored credentials on a privacy-positioned hosted product.
- Anything requiring LLM synthesis inside the “source of truth” layer.

---

## Builder checklist

1. **Schema first** — Define the context document (`as_of`, sections,
   `available` flags) before wiring MCP tool names.
2. **Ingest idempotency** — Source runs should be safe to retry; store
   append-only event or snapshot rows.
3. **Pure rollup** — No network I/O in rollup; read store only.
4. **Tool catalog** — One MCP tool per stable query shape; document args in
   machine-readable schemas.
5. **Setup objects** — Document `reason` codes; test missing-config paths.
6. **Privacy** — Pass through user secrets; do not log portfolio payloads.
7. **Payment semantics** — Align price with work (`freshness=cached` vs `live`).
8. **Publish the pattern** — Ship a public on-ramp doc so others can embed
   without reading your whole repo.

---

## Embed or license

AllocContext is [MIT licensed](../LICENSE). Self-host via PyPI; we do not operate
a public hosted MCP. **Inbound** embed/license inquiries via
[GitHub Issues](https://github.com/AllocContext/alloc-context/issues) only — no
outbound sales motion.

---

## Related

- [architecture.md](architecture.md) — repo pipeline and trust boundaries
- [context-bundle.md](context-bundle.md) — bundle schema reference
- [distribution.md](distribution.md) — registries and directory blurbs
- [examples.md](examples.md) — redacted tool output samples
