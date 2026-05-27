# ContextBundle

Deterministic facts document passed to the LLM. All narrative must trace to
fields here.

## Top-level shape

```json
{
  "bundle_id": "daily:2026-05-21T12:00:00Z",
  "scope": "daily",
  "as_of": "2026-05-21T12:00:00+00:00",
  "prior_as_of": "2026-05-20T12:00:00+00:00",
  "horizon_days": 90,
  "portfolio": { },
  "market": { },
  "sentiment": { },
  "macro": { },
  "delta": { },
  "regime": { }
}
```

## regime

Deterministic agent-facing hints synthesized from portfolio drift, sentiment,
and delta. No LLM.

| Field | Meaning |
|-------|---------|
| `summary` | Short combined hint line |
| `hints[]` | Structured `{kind, code, text}` entries |
| `allocation` | Drift band result (`hint`, `outside_band`, `max_drift`, `band`) |
| `volatility` | Kalshi short-horizon volatility regime when available |
| `sentiment` | Fear & Greed and Kalshi tape fields |
| `comparison` | `prior_as_of`, `notable_shifts` when a prior snapshot exists |

## portfolio

| Field | Source | Example |
|-------|--------|---------|
| `nav_usd` | Kraken API | `125432.10` |
| `cash_usd` | Kraken balances | `8200.00` |
| `allocation_pct` | Rollup | `{"BTC": 0.68, "ETH": 0.29, "CASH": 0.03}` |
| `target_allocation_pct` | Config | `{"BTC": 0.70, "ETH": 0.30}` |
| `drift` | Rollup | `{"BTC": -0.02, "ETH": -0.01}` |
| `pnl_usd.since_prior_snapshot` | Snapshots delta | `-420.00` |
| `rebalance_hint` | Rules | `"within_band"` / `"consider_deploy_cash"` |

## market

| Field | Source | Example |
|-------|--------|---------|
| `assets.btc.price_usd` | Kraken OHLC | `98500` |
| `assets.btc.change_pct.1_bar` | OHLC | `-1.2` |
| `assets.eth.change_pct.1_bar` | OHLC | `-0.8` |
| `breadth.feeds.coingecko` | CoinGecko ingest | dominance, rank, 24h change |
| `breadth.feeds.coinmarketcap` | CMC ingest | same fields (cross-check) |

## sentiment

| Field | Source | Example |
|-------|--------|---------|
| `fear_greed.value` | Alternative.me | `68` |
| `fear_greed.classification` | Rollup | `"Greed"` |
| `kalshi.tape_summary` | Kalshi ingest | `"mixed, BTC leading down"` |
| `kalshi.weighted_drift_5m_pct` | Cluster | `-0.04` |
| `kalshi.leaders_agree` | Cluster | `false` |
| `kalshi.sentiment_up_frac` | Cluster | `0.42` |

## macro

| Field | Source | Example |
|-------|--------|---------|
| `events.past_24h` | Calendar | `[{"name": "CPI", "impact": "high", ...}]` |
| `events.next_7d` | Calendar | `[...]` |
| `indicators.DGS10` | FRED ingest | latest yield + 7d/30d change |
| `etf.net_flow_usd.24h` | ETF ingest (optional) | `null` |

## delta

Computed vs the prior archived brief when `prior_as_of` is set (otherwise
falls back to recent snapshots where noted):

- `portfolio_nav_change_usd`
- `fear_greed_change`
- `market.btc_change_pct_since_prior`
- `market.eth_change_pct_since_prior`
- `notable_shifts[]` — deterministic rule hits for LLM emphasis

## JSON Schema

Formal schema: [schemas/context-bundle.v1.json](../schemas/context-bundle.v1.json)

## Synthesis contract

LLM input = ContextBundle JSON + `portfolio.notes` from config + system prompt.

LLM output = markdown sections:

1. Portfolio snapshot
2. What changed since last brief
3. Market + sentiment read
4. Calendar / catalysts
5. Forward watches (conditional bullets for the prediction log)
6. Observations (not instructions)
7. Not financial advice

Bounded suggestions allowed (“allocation drift suggests reviewing deploy
timing”) — never “buy” or “sell” as imperatives.
