# MCP tool output examples

Redacted samples from hosted tools (`freshness=cached`). Values are
illustrative — your `as_of`, prices, and NAV will differ. Not financial advice.

> **Privacy:** nothing stored · one-time read-only · pass-through only.

Full schema: [context-bundle.md](context-bundle.md). Tool args: [mcp.md](mcp.md).

## `get_context_bundle` (default — no allocation analysis)

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
    "cash_usd": 6200.0,
    "holdings": [
      {
        "symbol": "BTC",
        "qty": 0.85,
        "price_usd": 98500.0,
        "value_usd": 83725.0,
        "weight_pct": 0.67,
        "kind": "band"
      },
      {
        "symbol": "ETH",
        "qty": 11.2,
        "price_usd": 3200.0,
        "value_usd": 35840.0,
        "weight_pct": 0.287,
        "kind": "band"
      },
      {
        "symbol": "USD",
        "qty": 6200.0,
        "price_usd": 1.0,
        "value_usd": 6200.0,
        "weight_pct": 0.05,
        "kind": "cash"
      }
    ],
    "allocation_pct": {"BTC": 0.67, "ETH": 0.287, "CASH": 0.05}
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
    "allocation": {"available": false},
    "summary": "Fear & Greed index: 52 (Neutral)."
  },
  "delta": {
    "available": true,
    "notable_shifts": ["F&G 55 → 52 (-3)"]
  }
}
```

## `get_context_bundle` (with `target_pct` — allocation analysis)

```json
{
  "allocation_analysis": {
    "available": true,
    "allocation_pct": {"BTC": 0.67, "ETH": 0.287, "CASH": 0.05},
    "target_allocation_pct": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
    "drift": {"BTC": -0.03, "ETH": -0.013, "CASH": 0.05},
    "rebalance_hint": "within_band",
    "outside_band": false,
    "max_drift": 0.05,
    "band": 0.15
  },
  "regime": {
    "available": true,
    "allocation": {
      "available": true,
      "hint": "within_band",
      "outside_band": false,
      "max_drift": 0.05,
      "band": 0.15
    },
    "summary": "Portfolio allocation is within the configured drift band."
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
