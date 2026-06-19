# On-chain supply profit/loss cycle (ADR-021)

Slow-cycle BTC market structure from supply in profit vs supply in loss.
Complements tactical `regime.risk_off` (Fear & Greed) without mixing layers.

## Ingest source

| Property | Value |
|----------|-------|
| Source key | `onchain_cycle` |
| Default | Optional (`ingest.optional_sources`) |
| Cadence | Daily UTC bucket |
| Asset | BTC only (v1) |

Enable in host config:

```yaml
ingest:
  sources:
    onchain_cycle: true
  optional_sources:
    - onchain_cycle
```

## Default provider: Bitview (BRK)

Base URL: `https://bitview.space` (`onchain.cycle.bitview_base_url`).

Health pre-check: `GET /health` (must report `status: healthy`).

Bulk ingest (one call per refresh):

```http
GET /api/series/bulk?index=day&series=supply_in_profit_share,supply_in_loss_share,supply_in_profit,supply_in_loss&start=-14
```

On empty SQLite table, `start=-{backfill_days}` (default 3650).

| Bitview series | Stored field |
|----------------|--------------|
| `supply_in_profit_share` | `supply_profit_pct` |
| `supply_in_loss_share` | `supply_loss_pct` |
| `supply_in_profit` | `supply_profit_btc` |
| `supply_in_loss` | `supply_loss_btc` |

Day index `0` = 2009-01-01 (BRK `day1` origin).

## Alternate providers

| Provider | Config | Credential |
|----------|--------|------------|
| `bitview` | default | none |
| `brk` | `onchain.cycle.brk_base_url` | none |
| `glassnode` | `onchain.cycle.provider: glassnode` | `GLASSNODE_API_KEY` env |

## Bundle: `regime.cycle`

When data is fresh (≤ `max_staleness_days`, default 3):

- `phase`: `CAPITULATION` | `EUPHORIA` | `DISTRIBUTION` | `RECOVERY` | `NEUTRAL`
- `convergence`: `spread_pct ≤ convergence_spread_pct` (default 5)
- `history_7d`: deltas vs nearest row ≥ 7 days ago

When ingest skipped, provider fails, or data is stale: `available: false` with
`reason` (`provider_error`, `provider_unavailable`, `stale_data`,
`insufficient_history`, `missing_glassnode_key`).

Phase thresholds live under `regime.cycle.*` in config.

## Boundary

`regime.cycle` does **not** feed `regime.risk_off` or `regime.comparison.posture`.
Orchestrator and operator consume it as an external slow-cycle fact.
