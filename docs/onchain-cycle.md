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

Host must be on the allowlist (default: `bitview.space` only). HTTPS required;
no path suffix — same validation pattern as Kalshi base URLs.

Health pre-check: `GET /health` (must report `status: healthy`).

Bulk ingest (one call per refresh):

```http
GET /api/series/bulk?index=day&series=supply_in_profit_share,supply_in_loss_share,supply_in_profit,supply_in_loss&start=-14
```

On empty SQLite table, `start=-{backfill_days}` (default 3650). Rows with
`as_of_date` after today (UTC) are dropped before upsert.

| Bitview series | Stored field |
|----------------|--------------|
| `supply_in_profit_share` | `supply_profit_pct` |
| `supply_in_loss_share` | `supply_loss_pct` |
| `supply_in_profit` | `supply_profit_btc` |
| `supply_in_loss` | `supply_loss_btc` |

Day index `0` = 2009-01-01 (BRK `day1` origin).

## Self-hosted BRK

| Provider | Config | Credential |
|----------|--------|------------|
| `bitview` | default | none |
| `brk` | `onchain.cycle.brk_base_url` + `brk_allowed_hosts` | none |

Self-host operators must list the BRK hostname in `brk_allowed_hosts` (HTTPS,
host allowlist). Example:

```yaml
onchain:
  cycle:
    provider: brk
    brk_base_url: https://brk.example.com
    brk_allowed_hosts: [brk.example.com]
```

## Bundle: `regime.cycle`

Rollup uses the latest stored row with `as_of_date <=` the bundle reference
date (snapshot `as_of` for historical/replay paths).

When data is fresh (≤ `max_staleness_days`, default 3):

- `phase`: `CAPITULATION` | `EUPHORIA` | `DISTRIBUTION` | `RECOVERY` | `NEUTRAL`
- `convergence`: `spread_pct ≤ convergence_spread_pct` (default 5)
- `history_7d`: deltas vs nearest row between `history_7d_min_days` and
  `history_7d_max_days` ago (defaults 7–14)

When ingest skipped, provider fails, or data is stale: `available: false` with
`reason` (`provider_error`, `provider_unavailable`, `stale_data`,
`insufficient_history`).

Phase thresholds live under `regime.cycle.*` in config.

## Boundary

`regime.cycle` does **not** feed `regime.risk_off` or `regime.comparison.posture`.
Orchestrator and operator consume it as an external slow-cycle fact.
