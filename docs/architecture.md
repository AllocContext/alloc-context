# Architecture

## Purpose

**AllocContext** — one pipeline from **raw market facts** to **human briefs**
and (planned) **agent MCP tools**. Exchange APIs and third-party feeds are
**data sources only** — no order placement, no gate authority, no bot shadow
modes.

Agent-facing MCP + x402 plan: [mcp-roadmap.md](mcp-roadmap.md).

## Pipeline

```text
┌──────────────────────────────────────────────────────────────────┐
│                         alloc-context                            │
├──────────────────────────────────────────────────────────────────┤
│  ingest/          Scheduled pulls → normalized rows               │
│  store/           SQLite append-only snapshots                    │
│  rollup/          ContextBundle (deterministic, reproducible)     │
│  synthesize/      LLM prose from ContextBundle only               │
│  brief/           daily + weekly orchestration                    │
│  deliver/         Email, stdout, archived markdown                │
└──────────────────────────────────────────────────────────────────┘
```

## Trust boundaries

| Layer | LLM? | Places orders? |
|-------|------|----------------|
| Ingest | No | No |
| Rollup | No | No |
| Synthesize | Yes (narrative only) | No |
| Deliver | No | No |

## Data horizon

One quarterly window (`horizon.days: 90` by default) for everything persisted:
market bars, sentiment history, portfolio snapshots, brief archive rows,
prediction log, and markdown brief files under `state/briefs/`. Rollups and
LLM context should not assume data older than this unless explicitly archived
off-system.

The LLM **never** sees raw API credentials, never calls exchanges, and must
not invent numbers absent from the ContextBundle. Prompts require citing
deltas (“F&G 72 → 68 since prior brief”).

## ContextBundle

JSON document at a point in time. See [context-bundle.md](context-bundle.md).

Sections:

- `portfolio` — Kraken NAV, allocation, drift vs target, P&L windows
- `market` — BTC/ETH OHLC-derived signals
- `sentiment` — Kalshi cluster, F&G, optional breadth
- `macro` — calendar events past 24h / next 7d, ETF flows when enabled
- `delta` — changes since last daily brief

## Daily vs weekly

| | Daily | Weekly |
|---|--------|--------|
| Focus | Overnight moves, today’s calendar, portfolio drift | Regime recap, what mattered, forward week |
| Length | Short (email-friendly) | Longer synthesis |
| Archive | `state/briefs/daily/YYYY-MM-DD.md` | `state/briefs/weekly/YYYY-Www.md` |

## Alerts

Optional threshold notifications (allocation band breach) reuse ingest +
rollup; delivery policy lives in `deliver/alerts.py`. Scheduled briefs always
send; alerts respect cooldowns (`min_hours_between`, `max_per_7d`, `dedupe_hours`).

Enable in config:

```yaml
deliver:
  alerts:
    enabled: true
    triggers:
      rebalance_band: true
```

After each ingest, band breach triggers an email when policy allows. The band
uses `portfolio.rebalance_band` (default ±15% drift vs target).

## Prediction log

Daily and weekly briefs include a **Forward watches** section with bullets:

`- IF [condition] | WATCH [what to monitor] | BY [timeframe]`

Parsed watches are stored in `brief_predictions`. Run
`python -m alloccontext review monthly` to score them against current facts
(optional `--apply` to persist LLM scores).

## Optional self-hosting

Linux + systemd timers for scheduled ingest and email briefs are documented in
[self-hosting.md](self-hosting.md). Not required for MCP consumers.

## Non-goals

- Automated trade execution
- Holding user exchange secrets on a shared MCP server (BYOK in request only)
- Backtest / replay engines
- Multi-user SaaS
