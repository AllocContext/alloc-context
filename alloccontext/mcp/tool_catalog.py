"""Canonical MCP tool registry — descriptions, schemas, Bazaar/Smithery metadata."""

from __future__ import annotations

from typing import Any

from alloccontext.rollup.expectation_review import (
    REGIME_POSTURE_VALUES,
    REGIME_TRAJECTORY_VALUES,
    V0_CLAIM_TYPES,
)

READ_ONLY_ANNOTATIONS: dict[str, bool] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

OPEN_WORLD_READ_ANNOTATIONS: dict[str, bool] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

_TOOL_TITLES: dict[str, str] = {
    "get_market_context": "Get Market Context",
    "get_context_bundle": "Get Context Bundle",
    "get_expectation_review": "Get Expectation Review",
    "get_rebalance_plan": "Get Rebalance Plan",
    "get_portfolio_state": "Get Portfolio State",
    "check_allocation_band": "Check Allocation Band",
    "get_context_at": "Get Context at Timestamp",
    "get_context_delta": "Get Context Delta",
    "check_allocation_bands": "Check Allocation Bands",
}

_OPEN_WORLD_TOOLS = frozenset({"get_portfolio_state", "get_market_context", "get_context_bundle"})


def tool_title(tool_name: str) -> str:
    return _TOOL_TITLES.get(tool_name, tool_name.replace("_", " ").title())


def tool_annotations(tool_name: str) -> dict[str, bool]:
    if tool_name in _OPEN_WORLD_TOOLS:
        return dict(OPEN_WORLD_READ_ANNOTATIONS)
    return dict(READ_ONLY_ANNOTATIONS)


def pct_key_properties(*, role: str) -> dict[str, dict[str, Any]]:
    return {
        "BTC": {
            "type": "number",
            "description": f"{role} Bitcoin weight as a fraction of NAV (0–1).",
        },
        "ETH": {
            "type": "number",
            "description": f"{role} Ethereum weight as a fraction of NAV (0–1).",
        },
        "CASH": {
            "type": "number",
            "description": f"{role} cash/stablecoin weight as a fraction of NAV (0–1).",
        },
    }


def symbol_weight_map_schema(*, role: str, required: bool = True) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "description": (
            f"{role} NAV weight fractions (0–1) keyed by symbol; up to 20 symbols; "
            "values need not sum to 1."
        ),
        "additionalProperties": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "properties": pct_key_properties(role=role),
    }
    if required:
        schema["minProperties"] = 1
    schema["maxProperties"] = 20
    return schema


def allocation_pct_schema(*, role: str = "Current") -> dict[str, Any]:
    return {
        "type": "object",
        "description": (
            f"{role} NAV weight fractions keyed by symbol (0–1); "
            "cash/stables may use CASH."
        ),
        "additionalProperties": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "properties": pct_key_properties(role=role),
    }


SCOPE_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": ["daily", "weekly"],
    "description": "Rollup scope: daily (default) or weekly.",
}

FRESHNESS_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": ["cached", "live"],
    "description": (
        "cached: read local ingest DB only. live: run ingest first "
        "(requires ingest API keys on the host)."
    ),
}

ASSET_FILTER_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "string", "enum": ["BTC", "ETH", "CASH"]},
    "description": (
        "Optional asset symbols for market fields (default BTC and ETH), "
        "e.g. ['BTC', 'ETH', 'HYPE']."
    ),
}

TARGET_PCT_SCHEMA: dict[str, Any] = symbol_weight_map_schema(role="Target")

OPTIONAL_TARGET_PCT_SCHEMA: dict[str, Any] = symbol_weight_map_schema(
    role="Target",
    required=False,
)

BAND_SCHEMA: dict[str, Any] = {
    "type": "number",
    "description": "Drift band width as a fraction (e.g. 0.15 = 15% outside target).",
}

THESES_SCHEMA: dict[str, Any] = {
    "type": "array",
    "description": (
        "Optional local thesis entries for expectation_review (pass-through; "
        "nothing stored). Each entry requires id, recorded_at, and claims[]. "
        f"Supported claim types: {', '.join(sorted(V0_CLAIM_TYPES))}."
    ),
    "items": {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "Stable thesis identifier for claim results.",
            },
            "recorded_at": {
                "type": "string",
                "description": "Thesis anchor ISO timestamp (baseline snapshot).",
            },
            "asset": {
                "type": "string",
                "description": "Optional context symbol for the thesis (not scored).",
            },
            "claims": {
                "type": "array",
                "description": "Structured claim objects scored deterministically.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": sorted(V0_CLAIM_TYPES),
                            "description": (
                                "Claim type. Asset-scoped: PRICE_STRENGTH, "
                                "RELATIVE_STRENGTH, ALLOCATION_FIT (requires asset). "
                                "Market-wide: MARKET_SENTIMENT, VOLATILITY_REGIME, "
                                "RISK_APPETITE, REGIME_EXPECTATION."
                            ),
                        },
                        "asset": {
                            "type": "string",
                            "description": (
                                "Held asset symbol for PRICE_STRENGTH, "
                                "RELATIVE_STRENGTH, or ALLOCATION_FIT."
                            ),
                        },
                        "benchmark": {
                            "type": "string",
                            "description": "Benchmark symbol for RELATIVE_STRENGTH (default BTC).",
                        },
                        "direction": {
                            "type": "string",
                            "description": (
                                "Expected direction: PRICE_STRENGTH (UP/DOWN); "
                                "MARKET_SENTIMENT (IMPROVING/WEAKENING); "
                                "VOLATILITY_REGIME (DECREASING/INCREASING); "
                                "RISK_APPETITE (INCREASING/DECREASING)."
                            ),
                        },
                        "posture": {
                            "type": "string",
                            "enum": list(REGIME_POSTURE_VALUES),
                            "description": (
                                "Required for REGIME_EXPECTATION — expected "
                                "ADR-015 posture label (regime.comparison.posture)."
                            ),
                        },
                        "trajectory": {
                            "type": "string",
                            "enum": list(REGIME_TRAJECTORY_VALUES),
                            "description": (
                                "Optional for REGIME_EXPECTATION — expected 7d "
                                "posture trajectory (IMPROVING/STABLE/DETERIORATING)."
                            ),
                        },
                    },
                    "required": ["type"],
                },
            },
            "rationale": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Agent context only — never scored.",
            },
        },
        "required": ["id", "recorded_at", "claims"],
    },
}

MATCH_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": ["exact", "at_or_before", "thesis_baseline"],
    "description": (
        "exact: snapshot at as_of only. at_or_before (default): latest "
        "snapshot on or before as_of. thesis_baseline: earliest snapshot "
        "when recorded_at predates saved history."
    ),
}

EXPECTATION_REPLAY_SCHEMA: dict[str, Any] = {
    "type": "boolean",
    "description": (
        "When true with theses[], attach expectation_review.replay "
        "(counterfactual claim timeline)."
    ),
}

AS_OF_SCHEMA: dict[str, Any] = {
    "type": "string",
    "description": "ISO-8601 timestamp for the snapshot to load.",
}

PRIOR_AS_OF_SCHEMA: dict[str, Any] = {
    "type": "string",
    "description": "ISO-8601 timestamp of the earlier snapshot (required).",
}

CURRENT_AS_OF_SCHEMA: dict[str, Any] = {
    "type": "string",
    "description": (
        "ISO-8601 timestamp of the later snapshot; omit for latest live bundle."
    ),
}

SCENARIOS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "description": (
        "Scenario objects, each with required target_pct and optional name "
        "and band (default 0.15)."
    ),
    "items": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Optional label for this scenario (e.g. base, conservative).",
            },
            "target_pct": {
                "type": "object",
                "description": "Target weights for this scenario.",
                "properties": pct_key_properties(role="Target"),
                "required": ["BTC", "ETH", "CASH"],
            },
            "band": BAND_SCHEMA,
        },
        "required": ["target_pct"],
    },
}


NAV_USD_SCHEMA: dict[str, Any] = {
    "type": "number",
    "description": "Portfolio net asset value in USD.",
}

EXCHANGE_KRAKEN_COINBASE_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": ["kraken", "coinbase"],
    "description": "Spot exchange for move wording: kraken (default) or coinbase.",
}

EXCHANGE_REQUIRED_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": ["kraken", "coinbase", "wallet"],
    "description": "Portfolio source: kraken, coinbase, or wallet (EVM address).",
}

WALLET_ADDRESS_SCHEMA: dict[str, Any] = {
    "type": "string",
    "description": "EVM wallet address (0x + 40 hex). Required when exchange=wallet.",
}

API_KEY_SCHEMA: dict[str, Any] = {
    "type": "string",
    "description": "Read-only exchange API key (Coinbase CDP key name).",
}

API_SECRET_SCHEMA: dict[str, Any] = {
    "type": "string",
    "description": (
        "Read-only API secret (Kraken base64 secret or Coinbase EC PEM)."
    ),
}

BAND_DEFAULT_SCHEMA: dict[str, Any] = {
    "type": "number",
    "description": "Drift band width as a fraction (default 0.15 = 15%).",
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "get_context_bundle": (
        "Return the full read-only ContextBundle JSON: portfolio holdings, "
        "market, sentiment, macro, regime hints, and delta vs the prior saved "
        "snapshot. Use get_market_context for market-only; use get_context_at "
        "for a historical snapshot; use get_context_delta to compare two times. "
        "Optional target_pct and band attach allocation_analysis (opt-in drift "
        "math). Optional theses[] attaches expectation_review (deterministic "
        "claim scoring vs recorded_at baseline; pass-through only). Optional "
        "expectation_replay=true adds a counterfactual timeline when theses[] "
        "is supplied. freshness=cached uses the local ingest DB; freshness=live runs "
        "ingest first (may add latency; needs ingest API keys on the host)."
    ),
    "get_expectation_review": (
        "Score local theses deterministically against saved snapshots — same "
        "rules as expectation_review on get_context_bundle, without returning "
        "the full ContextBundle. Requires theses[] (pass-through only; nothing "
        "stored). Optional target_pct and band for ALLOCATION_FIT claims; "
        "expectation_replay=true adds a counterfactual timeline."
    ),
    "get_market_context": (
        "Return read-only fused market backdrop: sentiment (Fear & Greed, "
        "Kalshi), macro events, FRED indicators, ETF flows, and market breadth "
        "(no portfolio holdings). Use get_context_bundle when you also need "
        "holdings, delta, or regime. freshness=cached uses the local ingest DB; "
        "freshness=live runs ingest first (requires ingest API keys on the host)."
    ),
    "get_rebalance_plan": (
        "Compute read-only USD deltas and suggested exchange move lines to "
        "reach a target allocation map. Pure math — no exchange API calls. "
        "Requires allocation_pct, target_pct, and nav_usd. Evaluates every "
        "symbol in target_pct (same model as allocation_analysis). Optional "
        "pairs map overrides exchange product ids per symbol. Use "
        "get_portfolio_state or get_context_bundle when you need live or cached "
        "weights first. Use check_allocation_band for pass/fail drift only; use "
        "check_allocation_bands for multiple scenarios. Optional band adds a "
        "band_check block alongside the plan. exchange=kraken|coinbase adjusts "
        "move wording only."
    ),
    "get_portfolio_state": (
        "Fetch live read-only portfolio NAV, holdings[], and band weights from "
        "a supported source: CEX (Kraken or Coinbase read-only API keys in this "
        "call, never stored) or wallet (public EVM address — keyless for the "
        "caller). exchange=wallet requires wallet_address; CEX paths require "
        "api_key and "
        "api_secret. Use get_context_bundle for cached market without keys. "
        "Optional target_pct attaches allocation_analysis; optional band sets drift "
        "width when target_pct is supplied. Fail-closed on errors — no side effects."
    ),
    "check_allocation_band": (
        "Read-only drift check: are current symbol weights outside the drift "
        "band vs target_pct? Evaluates every symbol in the target map. Returns "
        "hint within_band or consider_rebalance. Requires allocation_pct and "
        "target_pct; band defaults to 0.15. Single-scenario only — use "
        "check_allocation_bands for multiple targets in one call. Use "
        "get_rebalance_plan when you need USD move lines for the same symbols. "
        "For bundle drift, pass target_pct on get_context_bundle to attach "
        "allocation_analysis instead."
    ),
    "get_context_at": (
        "Load a read-only ContextBundle snapshot from ingest history at a "
        "point in time. Use get_context_bundle for the latest snapshot; use "
        "get_context_delta to compare two timestamps. Read-only; returns an "
        "unavailable payload when no snapshot matches as_of and match. Optional "
        "target_pct and band attach allocation_analysis to the historical bundle."
    ),
    "get_context_delta": (
        "Compare two read-only ContextBundle snapshots and return "
        "notable_shifts between them. Requires prior_as_of; omit current_as_of "
        "to diff against the latest live bundle. Use get_context_at to load one "
        "snapshot without diffing. Read-only; no ingest unless you combine with "
        "a live current_as_of path."
    ),
    "check_allocation_bands": (
        "Read-only batch drift check: evaluate allocation_pct against multiple "
        "target_pct/band scenarios in one call. Each scenario requires "
        "target_pct; optional name and band (default 0.15). Use "
        "check_allocation_band for a single target. Use get_rebalance_plan when "
        "you need USD move lines after identifying drift."
    ),
}

MCP_TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "tool_name": "get_market_context",
        "description": TOOL_DESCRIPTIONS["get_market_context"],
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": SCOPE_SCHEMA,
                "freshness": FRESHNESS_SCHEMA,
                "assets": ASSET_FILTER_SCHEMA,
            },
        },
        "example": {"scope": "daily", "freshness": "cached", "assets": ["BTC", "ETH"]},
        "output_example": {
            "scope": "daily",
            "freshness": "cached",
            "as_of": "2026-05-21T12:00:00+00:00",
            "age_seconds": 3600,
            "sentiment": {"available": True},
            "macro": {"available": True, "sources": []},
            "etf": {"available": True, "assets": {}},
            "breadth": {"available": True},
        },
    },
    {
        "tool_name": "get_context_bundle",
        "description": TOOL_DESCRIPTIONS["get_context_bundle"],
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": SCOPE_SCHEMA,
                "freshness": FRESHNESS_SCHEMA,
                "assets": ASSET_FILTER_SCHEMA,
                "target_pct": TARGET_PCT_SCHEMA,
                "band": BAND_SCHEMA,
                "theses": THESES_SCHEMA,
                "expectation_replay": EXPECTATION_REPLAY_SCHEMA,
            },
        },
        "example": {
            "scope": "daily",
            "freshness": "cached",
            "assets": ["BTC", "ETH"],
        },
        "output_example": {
            "bundle_id": "daily:2026-05-21T12:00:00+00:00",
            "scope": "daily",
            "assets": ["BTC", "ETH"],
            "portfolio": {
                "available": True,
                "holdings": [{"symbol": "BTC", "kind": "band"}],
            },
            "market": {"available": True},
            "sentiment": {"available": True},
            "macro": {"available": True},
            "regime": {
                "available": True,
                "allocation": {"available": False},
                "summary": "Fear & Greed index: 52 (Neutral).",
            },
            "delta": {"available": True},
        },
    },
    {
        "tool_name": "get_expectation_review",
        "description": TOOL_DESCRIPTIONS["get_expectation_review"],
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": SCOPE_SCHEMA,
                "freshness": FRESHNESS_SCHEMA,
                "theses": THESES_SCHEMA,
                "target_pct": TARGET_PCT_SCHEMA,
                "band": BAND_SCHEMA,
                "expectation_replay": EXPECTATION_REPLAY_SCHEMA,
            },
            "required": ["theses"],
        },
        "example": {
            "scope": "daily",
            "freshness": "cached",
            "theses": [
                {
                    "id": "btc-thesis",
                    "recorded_at": "2026-06-01T00:00:00Z",
                    "claims": [
                        {
                            "type": "PRICE_STRENGTH",
                            "asset": "BTC",
                            "direction": "UP",
                        }
                    ],
                }
            ],
        },
        "output_example": {
            "scope": "daily",
            "freshness": "cached",
            "as_of": "2026-06-10T12:00:00+00:00",
            "age_seconds": 3600,
            "available": True,
            "baseline_as_of": "2026-06-01T00:00:00Z",
            "current_as_of": "2026-06-10T12:00:00+00:00",
            "supported": 1,
            "weakened": 0,
            "unknown": 0,
            "claims": [],
        },
    },
    {
        "tool_name": "get_rebalance_plan",
        "description": TOOL_DESCRIPTIONS["get_rebalance_plan"],
        "input_schema": {
            "type": "object",
            "properties": {
                "allocation_pct": allocation_pct_schema(role="Current"),
                "target_pct": allocation_pct_schema(role="Target"),
                "nav_usd": NAV_USD_SCHEMA,
                "exchange": EXCHANGE_KRAKEN_COINBASE_SCHEMA,
                "band": BAND_SCHEMA,
            },
            "required": ["allocation_pct", "target_pct", "nav_usd"],
        },
        "example": {
            "allocation_pct": {"BTC": 0.45, "ETH": 0.45, "CASH": 0.10},
            "target_pct": {"BTC": 0.50, "ETH": 0.40, "CASH": 0.10},
            "nav_usd": 10000,
            "exchange": "kraken",
            "band": 0.15,
        },
        "output_example": {
            "as_of": "2026-05-21T12:00:00+00:00",
            "age_seconds": 0,
            "exchange": "kraken",
            "moves": [],
            "deltas_usd": {"BTC": 500.0, "ETH": -500.0, "CASH": 0.0},
            "band_check": {"outside_band": False, "hint": "within_band"},
        },
    },
    {
        "tool_name": "get_portfolio_state",
        "description": TOOL_DESCRIPTIONS["get_portfolio_state"],
        "input_schema": {
            "type": "object",
            "properties": {
                "exchange": EXCHANGE_REQUIRED_SCHEMA,
                "api_key": API_KEY_SCHEMA,
                "api_secret": API_SECRET_SCHEMA,
                "wallet_address": WALLET_ADDRESS_SCHEMA,
                "target_pct": OPTIONAL_TARGET_PCT_SCHEMA,
                "band": BAND_SCHEMA,
            },
            "required": ["exchange"],
        },
        "example": {
            "exchange": "wallet",
            "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
        },
        "output_example": {
            "available": True,
            "exchange": "kraken",
            "source": "live",
            "as_of": "2026-05-21T12:00:00+00:00",
            "age_seconds": 0,
            "nav_usd": 10000.0,
            "holdings": [{"symbol": "BTC", "kind": "band"}],
            "allocation_pct": {"BTC": 0.70, "ETH": 0.25, "CASH": 0.05},
        },
    },
    {
        "tool_name": "check_allocation_band",
        "description": TOOL_DESCRIPTIONS["check_allocation_band"],
        "input_schema": {
            "type": "object",
            "properties": {
                "allocation_pct": allocation_pct_schema(role="Current"),
                "target_pct": allocation_pct_schema(role="Target"),
                "band": BAND_DEFAULT_SCHEMA,
            },
            "required": ["allocation_pct", "target_pct"],
        },
        "example": {
            "allocation_pct": {"BTC": 0.45, "ETH": 0.45, "CASH": 0.10},
            "target_pct": {"BTC": 0.50, "ETH": 0.40, "CASH": 0.10},
            "band": 0.15,
        },
        "output_example": {
            "as_of": "2026-05-21T12:00:00+00:00",
            "age_seconds": 0,
            "outside_band": False,
            "hint": "within_band",
            "max_drift": 0.05,
        },
    },
    {
        "tool_name": "get_context_at",
        "description": TOOL_DESCRIPTIONS["get_context_at"],
        "input_schema": {
            "type": "object",
            "properties": {
                "as_of": AS_OF_SCHEMA,
                "scope": SCOPE_SCHEMA,
                "match": MATCH_SCHEMA,
                "assets": ASSET_FILTER_SCHEMA,
                "target_pct": TARGET_PCT_SCHEMA,
                "band": BAND_SCHEMA,
            },
            "required": ["as_of"],
        },
        "example": {
            "as_of": "2026-05-21T12:00:00+00:00",
            "scope": "daily",
            "match": "at_or_before",
        },
        "output_example": {
            "scope": "daily",
            "as_of": "2026-05-21T12:00:00+00:00",
            "portfolio": {"available": True},
            "regime": {"available": True},
        },
    },
    {
        "tool_name": "get_context_delta",
        "description": TOOL_DESCRIPTIONS["get_context_delta"],
        "input_schema": {
            "type": "object",
            "properties": {
                "prior_as_of": PRIOR_AS_OF_SCHEMA,
                "scope": SCOPE_SCHEMA,
                "current_as_of": CURRENT_AS_OF_SCHEMA,
                "assets": ASSET_FILTER_SCHEMA,
            },
            "required": ["prior_as_of"],
        },
        "example": {
            "prior_as_of": "2026-05-20T12:00:00+00:00",
            "scope": "daily",
        },
        "output_example": {
            "prior_as_of": "2026-05-20T12:00:00+00:00",
            "current_as_of": "2026-05-21T12:00:00+00:00",
            "notable_shifts": ["F&G 30 → 25 (-5)"],
        },
    },
    {
        "tool_name": "check_allocation_bands",
        "description": TOOL_DESCRIPTIONS["check_allocation_bands"],
        "input_schema": {
            "type": "object",
            "properties": {
                "allocation_pct": allocation_pct_schema(role="Current"),
                "scenarios": SCENARIOS_SCHEMA,
            },
            "required": ["allocation_pct", "scenarios"],
        },
        "example": {
            "allocation_pct": {"BTC": 0.65, "ETH": 0.30, "CASH": 0.05},
            "scenarios": [
                {
                    "name": "base",
                    "target_pct": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.00},
                    "band": 0.15,
                }
            ],
        },
        "output_example": {
            "allocation_pct": {"BTC": 0.65, "ETH": 0.30, "CASH": 0.05},
            "scenarios": [{"name": "base", "hint": "within_band"}],
        },
    },
)

MCP_TOOL_NAMES: tuple[str, ...] = tuple(
    spec["tool_name"] for spec in MCP_TOOL_SPECS
)


def tool_description(tool_name: str) -> str:
    try:
        return TOOL_DESCRIPTIONS[tool_name]
    except KeyError as exc:
        raise KeyError(f"unknown MCP tool: {tool_name}") from exc


def mcp_tool_specs() -> tuple[dict[str, Any], ...]:
    return MCP_TOOL_SPECS


def tool_mcp_annotations(tool_name: str):
    """FastMCP ToolAnnotations for a registered tool (requires mcp package)."""
    from mcp.types import ToolAnnotations

    return ToolAnnotations(**tool_annotations(tool_name))


def output_schema_from_example(example: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for key, value in example.items():
        if isinstance(value, bool):
            prop_type: str | list[str] = "boolean"
        elif isinstance(value, int):
            prop_type = "integer"
        elif isinstance(value, float):
            prop_type = "number"
        elif isinstance(value, str):
            prop_type = "string"
        elif isinstance(value, list):
            prop_type = "array"
        elif isinstance(value, dict):
            prop_type = "object"
        else:
            prop_type = "string"
        properties[key] = {"type": prop_type}
    return {
        "type": "object",
        "description": "Deterministic JSON tool result from AllocContext.",
        "properties": properties,
        "additionalProperties": True,
    }


def server_card_tool_entry(spec: dict[str, Any]) -> dict[str, Any]:
    tool_name = spec["tool_name"]
    return {
        "name": tool_name,
        "title": tool_title(tool_name),
        "description": spec["description"],
        "inputSchema": spec["input_schema"],
        "outputSchema": output_schema_from_example(spec["output_example"]),
        "annotations": tool_annotations(tool_name),
    }


MCP_SERVER_PROMPTS: tuple[dict[str, Any], ...] = (
    {
        "name": "portfolio_context_review",
        "description": (
            "Load the latest portfolio-aware crypto context bundle, then "
            "summarize holdings, market sentiment, and notable regime shifts "
            "for the user."
        ),
        "arguments": [
            {
                "name": "scope",
                "description": "Rollup scope: daily or weekly.",
                "required": False,
            }
        ],
    },
    {
        "name": "allocation_drift_check",
        "description": (
            "Compare current BTC/ETH/CASH weights to a target allocation and "
            "report whether the portfolio is outside the drift band."
        ),
        "arguments": [
            {
                "name": "band",
                "description": "Drift band width as a fraction (default 0.15).",
                "required": False,
            }
        ],
    },
    {
        "name": "rebalance_planning",
        "description": (
            "Given current allocation weights and NAV, compute USD deltas and "
            "suggested exchange move lines toward a target split."
        ),
        "arguments": [
            {
                "name": "exchange",
                "description": "kraken or coinbase — affects move wording only.",
                "required": False,
            }
        ],
    },
    {
        "name": "context_time_travel",
        "description": (
            "Load a historical ContextBundle at a timestamp and diff it "
            "against the latest snapshot to highlight notable shifts."
        ),
        "arguments": [
            {
                "name": "prior_as_of",
                "description": "ISO-8601 timestamp of the earlier snapshot.",
                "required": True,
            }
        ],
    },
)

MCP_SERVER_RESOURCES: tuple[dict[str, Any], ...] = (
    {
        "uri": "context-bundle://schema/v2",
        "name": "ContextBundle schema v2",
        "description": "JSON Schema for portfolio-first ContextBundle responses.",
        "mimeType": "application/schema+json",
    },
    {
        "uri": "alloc-context://tools/rebalance-hints",
        "name": "Rebalance hint guide",
        "description": "Codes returned in allocation_analysis and band_check hints.",
        "mimeType": "text/markdown",
    },
)


def assert_input_schema_descriptions(schema: dict[str, Any], *, tool_name: str) -> None:
    """Raise AssertionError when any input property lacks a description."""
    props = schema.get("properties") or {}
    for name, spec in props.items():
        if not spec.get("description"):
            msg = f"{tool_name}.{name} missing inputSchema description"
            raise AssertionError(msg)
        nested = spec.get("properties") or {}
        for nested_name, nested_spec in nested.items():
            if not nested_spec.get("description"):
                msg = (
                    f"{tool_name}.{name}.{nested_name} missing "
                    "inputSchema description"
                )
                raise AssertionError(msg)
        items = spec.get("items")
        if isinstance(items, dict):
            item_props = items.get("properties") or {}
            for item_name, item_spec in item_props.items():
                if not item_spec.get("description"):
                    msg = (
                        f"{tool_name}.{name}[].{item_name} missing "
                        "inputSchema description"
                    )
                    raise AssertionError(msg)
