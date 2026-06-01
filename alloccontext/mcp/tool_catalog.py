"""Shared MCP tool metadata for Smithery server cards and FastMCP registration."""

from __future__ import annotations

from typing import Any

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


def allocation_pct_schema(*, role: str = "Current") -> dict[str, Any]:
    return {
        "type": "object",
        "description": (
            f"{role} BTC/ETH/CASH band weights; values typically sum to ~1."
        ),
        "properties": pct_key_properties(role=role),
        "required": ["BTC", "ETH", "CASH"],
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

TARGET_PCT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Optional target weights; when set, attaches allocation_analysis "
        "drift math to the response."
    ),
    "properties": pct_key_properties(role="Target"),
    "required": ["BTC", "ETH", "CASH"],
}

OPTIONAL_TARGET_PCT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Optional target weights; when set, attaches allocation_analysis "
        "to the portfolio response."
    ),
    "properties": pct_key_properties(role="Target"),
}

BAND_SCHEMA: dict[str, Any] = {
    "type": "number",
    "description": "Drift band width as a fraction (e.g. 0.15 = 15% outside target).",
}

MATCH_SCHEMA: dict[str, Any] = {
    "type": "string",
    "enum": ["exact", "at_or_before"],
    "description": (
        "exact: snapshot at as_of only. at_or_before (default): latest "
        "snapshot on or before as_of."
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
