# ContextBundle

Deterministic facts document passed to the LLM. All narrative must trace to
fields here.

**Privacy:** [USE.md](USE.md) — nothing stored · one-time read-only · pass-through only.

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

When allocation analysis is requested (`target_pct` / `band` on the tool, or
`target_allocation` in bridge user config), the bundle may also include:

```json
{
  "allocation_analysis": {
    "available": true,
    "allocation_pct": {"BTC": 0.68, "ETH": 0.27, "CASH": 0.05},
    "target_allocation_pct": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
    "drift": {"BTC": -0.02, "ETH": -0.03, "CASH": 0.05},
    "rebalance_hint": "within_band",
    "outside_band": false,
    "max_drift": 0.05,
    "band": 0.15
  }
}
```

## portfolio (default)

Portfolio-first: holdings and band weights. **No** embedded `target_allocation_pct`,
`drift`, or `rebalance_hint` unless you opt into `allocation_analysis`.

| Field | Meaning |
|-------|---------|
| `nav_usd` | Total NAV in USD |
| `cash_usd` | Stable / USD cash total |
| `holdings[]` | Recognized balances: `symbol`, `qty`, `price_usd`, `value_usd`, `weight_pct`, `kind` (`band` / `holding` / `cash`) |
| `allocation_pct` | Band weights only: `BTC`, `ETH`, `CASH` derived from holdings |
| `unrecognized[]` | Symbols seen in balances but without a USD mark |
| `prices` | USD marks used for valuation |
| `cash_breakdown` | Per-stable breakdown when available |
| `pnl_usd.since_prior_snapshot` | NAV change vs prior ingest snapshot |

Example holding:

```json
{
  "symbol": "HYPE",
  "qty": 10.0,
  "price_usd": 25.0,
  "value_usd": 250.0,
  "weight_pct": 0.002,
  "kind": "holding"
}
```

## allocation_analysis (opt-in)

Separate block when drift math is requested. Evaluates **current holdings
weights** vs the supplied target map (any symbols; values need not sum to 1).
`portfolio.allocation_pct` remains a band-collapsed BTC/ETH/CASH view for
backward compatibility — prefer `allocation_analysis.allocation_pct` for drift.

Same semantics as legacy portfolio drift fields. `regime.allocation` is
populated only when this block (or legacy compat fields) is present.

When `theses[]` includes an `ALLOCATION_FIT` claim, the server may attach
`allocation_analysis` automatically using configured `target_allocations` and
`rebalance_band` even if the tool call omits `target_pct` / `band`.

## expectation_review (opt-in)

Present when `theses[]` is supplied on `get_context_bundle` (tool argument or
bridge `user.yaml`). Pass-through beliefs only — nothing is stored server-side.

| Field | Meaning |
|-------|---------|
| `baseline_as_of` | Set only when every scored claim shares one baseline snapshot |
| `baseline_tolerance` | `earliest_available` when thesis `recorded_at` predates first snapshot |
| `current_as_of` | `as_of` of the current bundle |
| `supported` / `weakened` / `unknown` | Claim outcome counts |
| `claims[]` | Per-claim `{thesis_id, type, asset?, status, reason?, evidence}` |
| `replay` | Present when `expectation_replay=true`; checkpoint timeline + transitions |

Claim types (v0): `PRICE_STRENGTH`, `RELATIVE_STRENGTH`, `MARKET_SENTIMENT`,
`VOLATILITY_REGIME`, `RISK_APPETITE`, `REGIME_EXPECTATION`, `ALLOCATION_FIT`.
Each claim's
`evidence.baseline_as_of` identifies the snapshot used for that thesis.

`REGIME_EXPECTATION` uses ADR-015 posture enums: required `posture`
(`RISK_ON` | `NEUTRAL` | `RISK_OFF`); optional `trajectory`
(`IMPROVING` | `STABLE` | `DETERIORATING`). Scores current
`regime.comparison.posture` against the claim; evidence includes baseline and
current labels.

## regime

Deterministic agent-facing hints from **external** sentiment, volatility,
and market-wide delta shifts. Sleeve allocation drift and held-alt moves live
on `allocation_analysis` / `portfolio.material_moves` — not regime hints.

| Field | Meaning |
|-------|---------|
| `summary` | Short combined hint line (external signals only) |
| `hints[]` | Structured `{kind, code, text}` — sentiment, volatility, spot_prediction, delta (market shifts only) |
| `allocation` | Deprecated sleeve mirror when analysis ran; use `allocation_analysis` |
| `volatility` | Kalshi short-horizon volatility regime when available |
| `sentiment` | Fear & Greed and Kalshi tape fields |
| `comparison` | `prior_as_of`; `market_shifts` / `sleeve_shifts` (adjacent snapshot);
  `notable_shifts` mirrors `market_shifts`; `history[]` and `posture` (7d/30d) |
| `risk_off` | External-only market risk score (Fear & Greed in v1); not portfolio
  cash or rebalance hints |
| `cycle` | Slow-cycle BTC supply profit/loss phase (`docs/onchain-cycle.md`); optional ingest; does not feed `risk_off` |

Held-alt material moves: `portfolio.material_moves[]` when weight ≥10% and
move ≥5% (24h or since prior).

## market

| Field | Source | Example |
|-------|--------|---------|
| `assets.btc.price_usd` | Exchange OHLC | `98500` |
| `assets.btc.change_pct.1_bar` | OHLC | `-1.2` |
| `assets.eth.change_pct.1_bar` | OHLC | `-0.8` |
| `assets.hype.price_usd` | Alt quote snapshot (CMC/CG) | `25.1` |
| `assets.hype.change_pct.24h` | Alt quote snapshot | `1.2` |
| `assets.hype.source` | Alt quote snapshot | `"coingecko"` |
| `breadth.feeds.coingecko` | CoinGecko ingest | dominance, rank, 24h change |
| `breadth.feeds.coinmarketcap` | CMC ingest | same fields (cross-check) |

Band assets (BTC/ETH) use exchange OHLC bars. Alt holdings (e.g. HYPE) use
cached quote snapshots when available; missing alts appear in `assets_omitted[]`.

Use the `assets` tool argument to filter market/ETF fields (default `BTC`, `ETH`).
On the stdio bridge, omit `assets` to auto-scope from local portfolio holdings
(symbols only sent upstream).

## Market coverage

What each symbol class gets in a ContextBundle (ADR-009):

| Class | Symbols | Ingest | ContextBundle fields |
|-------|---------|--------|----------------------|
| **Band** | BTC, ETH | CF benchmarks OHLC (Kraken); SoSoValue ETF flows | `market.assets.btc`, `market.assets.eth` — OHLC price + `change_pct.1_bar` |
| **Alt holdings** | Non-band, non-stable (e.g. HYPE) | Bounded quote snapshots (exchange mark → CMC → CoinGecko); scheduled + on-demand | `market.assets.{symbol}` — `price_usd`, `change_pct.24h`, `source` |
| **Stables / cash** | USD, USDC, … | Portfolio marks only | `portfolio.holdings[]`, `cash_usd`; excluded from market `assets` filter |
| **Global feeds** | Market-wide | Fear & Greed, Kalshi, macro calendar, FRED, breadth | `sentiment`, `macro`, `market.breadth`; ETF flows remain BTC/ETH-centric |

Missing alt data for a requested symbol → `assets_omitted[]` (fail-soft on
`freshness=cached`). `freshness=live` refreshes quotes for requested symbols
only (heavy x402 tier on hosted).

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

Computed vs the prior saved snapshot when `prior_as_of` is set:

- `portfolio_nav_change_usd`
- `fear_greed_change`
- `market.btc_change_pct_since_prior`
- `market.eth_change_pct_since_prior`
- `market.{symbol}_change_pct_since_prior` — held alt keys when both snapshots had marks
- `notable_shifts[]` — deterministic rule hits (≥2% since prior for market moves)

## Migration from v1 portfolio fields

| v1 (deprecated default) | v2 |
|-------------------------|-----|
| `portfolio.target_allocation_pct` | `allocation_analysis.target_allocation_pct` |
| `portfolio.drift` | `allocation_analysis.drift` |
| `portfolio.rebalance_hint` | `allocation_analysis.rebalance_hint` |
| (none) | `portfolio.holdings[]` |

Legacy hosted snapshots may still expose drift on `portfolio` until dependents
migrate; new bridge and self-host responses follow v2.

## JSON Schema

- Current: [schemas/context-bundle.v2.json](../schemas/context-bundle.v2.json)
- Legacy: [schemas/context-bundle.v1.json](../schemas/context-bundle.v1.json)

MCP resource: `context-bundle://schema/v2`

## Agent narrative (optional)

Downstream agents may turn ContextBundle JSON into markdown. A typical outline:

1. Portfolio snapshot (`holdings[]`, NAV)
2. What changed since the prior snapshot
3. Market + sentiment read
4. Calendar / catalysts
5. Optional allocation analysis (when present)
6. Observations (not instructions)
7. Not financial advice

Bounded suggestions allowed (“allocation drift suggests reviewing deploy
timing”) — never “buy” or “sell” as imperatives. This repository does not
call an LLM or send email.
