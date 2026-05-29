# MCP tool output examples

Redacted samples from hosted tools (`freshness=cached`). Values are
illustrative — your `as_of`, prices, and NAV will differ. Not financial advice.

Full schema: [context-bundle.md](context-bundle.md). Tool args: [mcp.md](mcp.md).

## `get_context_bundle` (excerpt)

```json
{
  "bundle_id": "daily:2026-05-28T12:00:00+00:00",
  "scope": "daily",
  "as_of": "2026-05-28T12:00:00+00:00",
  "freshness": "cached",
  "age_seconds": 1800,
  "portfolio": {
    "available": true,
    "nav_usd": 125000.0,
    "allocation_pct": {"BTC": 0.68, "ETH": 0.27, "CASH": 0.05},
    "target_allocation_pct": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
    "rebalance_hint": "within_band"
  },
  "sentiment": {
    "available": true,
    "fear_greed": {"value": 52, "classification": "Neutral"}
  },
  "macro": {
    "available": true,
    "indicators": {"DGS10": {"value": 4.25, "change_7d": -0.05}}
  },
  "regime": {
    "available": true,
    "summary": "Portfolio allocation is within the configured drift band."
  },
  "delta": {
    "available": true,
    "notable_shifts": ["F&G 55 → 52 (-3)"]
  }
}
```

## `get_rebalance_plan`

```json
{
  "as_of": "2026-05-28T12:00:00+00:00",
  "age_seconds": 0,
  "available": true,
  "exchange": "kraken",
  "allocation_pct": {"BTC": 0.45, "ETH": 0.45, "CASH": 0.10},
  "target_pct": {"BTC": 0.50, "ETH": 0.40, "CASH": 0.10},
  "nav_usd": 10000,
  "delta_usd": {"BTC": 500.0, "ETH": -500.0, "CASH": 0.0},
  "moves": [
    "Sell $500 ETH → Buy $500 BTC (Kraken-style wording)"
  ],
  "band_check": {
    "outside_band": true,
    "hint": "consider_rebalance",
    "max_drift": 0.05
  }
}
```

## `check_allocation_band`

```json
{
  "as_of": "2026-05-28T12:00:00+00:00",
  "age_seconds": 0,
  "available": true,
  "allocation_pct": {"BTC": 0.45, "ETH": 0.45, "CASH": 0.10},
  "target_pct": {"BTC": 0.50, "ETH": 0.40, "CASH": 0.10},
  "band": 0.15,
  "drift": {"BTC": -0.05, "ETH": 0.05, "CASH": 0.0},
  "max_drift": 0.05,
  "outside_band": false,
  "hint": "within_band"
}
```
