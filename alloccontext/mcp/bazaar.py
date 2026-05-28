from __future__ import annotations

import os
from typing import Any

from x402.extensions.bazaar import (
    DeclareMcpDiscoveryConfig,
    OutputConfig,
    declare_discovery_extension,
    declare_mcp_discovery_extension,
)

SERVICE_NAME = "AllocContext"
SERVICE_TITLE = (
    "AllocContext — BTC/ETH allocation drift, rebalance moves & market context"
)
# CDP Bazaar indexes service_name (≤32 chars) and up to five tags from payments.
BAZAAR_SERVICE_NAME = "AllocContext BTC/ETH MCP"
SERVICE_TAGS = (
    "btc",
    "eth",
    "rebalance",
    "allocation",
    "crypto",
    "portfolio",
    "drift",
    "bitcoin",
    "agent-tools",
    "mcp",
    "sentiment",
    "macro",
)
BAZAAR_INDEX_TAGS = ("btc", "eth", "rebalance", "allocation", "portfolio")

DISCOVERY_KEYWORD_MARKERS = (
    "portfolio allocation",
    "allocation drift",
    "rebalance plan",
    "fear and greed",
    "etf flows",
)

LISTING_DESCRIPTION = (
    "Deterministic BTC/ETH portfolio allocation context for AI agents: "
    "allocation drift and band checks, USD rebalance plans, fused market "
    "context (Fear & Greed, Kalshi sentiment, macro calendar, FRED "
    "indicators, ETF flows), live Kraken/Coinbase portfolio reads, and "
    "saved ContextBundle snapshots. Structured JSON only — no LLM."
)

_ASSET_FILTER_SCHEMA = {
    "type": "array",
    "items": {"type": "string", "enum": ["BTC", "ETH", "CASH"]},
    "description": "Subset market and ETF fields (default BTC and ETH).",
}

_TARGET_PCT_SCHEMA = {
    "type": "object",
    "description": "Target weights keyed by BTC, ETH, CASH.",
    "properties": {
        "BTC": {"type": "number"},
        "ETH": {"type": "number"},
        "CASH": {"type": "number"},
    },
    "required": ["BTC", "ETH", "CASH"],
}

_BAND_SCHEMA = {
    "type": "number",
    "description": "Drift band width (for example 0.15 = 15%).",
}

_MCP_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "tool_name": "get_market_context",
        "description": (
            "Fused market backdrop for BTC/ETH allocation: Fear & Greed, Kalshi "
            "sentiment, macro calendar, FRED indicators, ETF flows, and breadth. "
            "Use freshness=cached for hosted cache; freshness=live runs ingest "
            "first (requires ingest API keys on the host)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["daily", "weekly"],
                    "description": "Rollup horizon for macro and context bundle.",
                },
                "freshness": {
                    "type": "string",
                    "enum": ["cached", "live"],
                    "description": (
                        "cached reads the ingest DB; live runs ingest first "
                        "(requires ingest API keys on the host)."
                    ),
                },
                "assets": _ASSET_FILTER_SCHEMA,
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
        "description": (
            "Full ContextBundle JSON: portfolio allocation drift vs target, "
            "market, sentiment, macro, regime hints, and delta vs the prior "
            "saved snapshot. Optional assets, target_pct, and band override "
            "server config for drift math."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["daily", "weekly"],
                },
                "freshness": {
                    "type": "string",
                    "enum": ["cached", "live"],
                },
                "assets": _ASSET_FILTER_SCHEMA,
                "target_pct": _TARGET_PCT_SCHEMA,
                "band": _BAND_SCHEMA,
            },
        },
        "example": {
            "scope": "daily",
            "freshness": "cached",
            "assets": ["BTC", "ETH"],
            "target_pct": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
            "band": 0.15,
        },
        "output_example": {
            "bundle_id": "daily:2026-05-21T12:00:00+00:00",
            "scope": "daily",
            "assets": ["BTC", "ETH"],
            "portfolio": {"available": True},
            "market": {"available": True},
            "sentiment": {"available": True},
            "macro": {"available": True},
            "regime": {"available": True, "summary": "Portfolio allocation is within the configured drift band."},
            "delta": {"available": True},
        },
    },
    {
        "tool_name": "get_rebalance_plan",
        "description": (
            "Compute USD deltas and exchange-style move lines to rebalance a "
            "BTC/ETH/CASH portfolio toward target allocation from current "
            "weights and NAV. Pure math — rebalance plan for btc/eth splits."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "allocation_pct": {
                    "type": "object",
                    "description": "Current weights keyed by BTC, ETH, CASH.",
                    "properties": {
                        "BTC": {"type": "number"},
                        "ETH": {"type": "number"},
                        "CASH": {"type": "number"},
                    },
                    "required": ["BTC", "ETH", "CASH"],
                },
                "target_pct": {
                    "type": "object",
                    "description": "Target weights keyed by BTC, ETH, CASH.",
                    "properties": {
                        "BTC": {"type": "number"},
                        "ETH": {"type": "number"},
                        "CASH": {"type": "number"},
                    },
                    "required": ["BTC", "ETH", "CASH"],
                },
                "nav_usd": {
                    "type": "number",
                    "description": "Portfolio NAV in USD.",
                },
                "exchange": {
                    "type": "string",
                    "enum": ["kraken", "coinbase"],
                    "description": (
                        "Exchange-specific move wording (default kraken)."
                    ),
                },
                "band": _BAND_SCHEMA,
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
        "description": (
            "Live portfolio read: NAV, BTC/ETH/CASH allocation, drift vs "
            "target, and band hint. Pass read-only kraken or coinbase credentials "
            "in the request; never stored server-side."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "exchange": {
                    "type": "string",
                    "enum": ["kraken", "coinbase"],
                    "description": "Spot exchange to query.",
                },
                "api_key": {
                    "type": "string",
                    "description": "Read-only API key (CDP key name for Coinbase).",
                },
                "api_secret": {
                    "type": "string",
                    "description": (
                        "Read-only API secret (Kraken base64 secret or Coinbase EC PEM)."
                    ),
                },
                "target_pct": {
                    "type": "object",
                    "description": "Optional target weights; defaults to server config.",
                    "properties": {
                        "BTC": {"type": "number"},
                        "ETH": {"type": "number"},
                        "CASH": {"type": "number"},
                    },
                },
                "band": {
                    "type": "number",
                    "description": "Drift band width (default from server config).",
                },
            },
            "required": ["exchange", "api_key", "api_secret"],
        },
        "example": {
            "exchange": "kraken",
            "api_key": "YOUR_READ_ONLY_KEY",
            "api_secret": "YOUR_READ_ONLY_SECRET",
        },
        "output_example": {
            "available": True,
            "exchange": "kraken",
            "source": "live",
            "as_of": "2026-05-21T12:00:00+00:00",
            "age_seconds": 0,
            "nav_usd": 10000.0,
            "allocation_pct": {"BTC": 0.70, "ETH": 0.25, "CASH": 0.05},
            "rebalance_hint": "within_band",
        },
    },
    {
        "tool_name": "check_allocation_band",
        "description": (
            "Check whether BTC/ETH/CASH allocation is outside a drift band vs "
            "target and return hint (within_band, consider_rebalance, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "allocation_pct": {
                    "type": "object",
                    "properties": {
                        "BTC": {"type": "number"},
                        "ETH": {"type": "number"},
                        "CASH": {"type": "number"},
                    },
                    "required": ["BTC", "ETH", "CASH"],
                },
                "target_pct": {
                    "type": "object",
                    "properties": {
                        "BTC": {"type": "number"},
                        "ETH": {"type": "number"},
                        "CASH": {"type": "number"},
                    },
                    "required": ["BTC", "ETH", "CASH"],
                },
                "band": {
                    "type": "number",
                    "description": "Drift band width (default 0.15 = 15%).",
                },
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
        "description": (
            "Load a saved ContextBundle snapshot from ingest history by ISO "
            "timestamp (match exact or at_or_before)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "as_of": {"type": "string", "description": "ISO timestamp."},
                "scope": {"type": "string", "enum": ["daily", "weekly"]},
                "match": {"type": "string", "enum": ["exact", "at_or_before"]},
                "assets": _ASSET_FILTER_SCHEMA,
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
        "description": (
            "Compare two ContextBundle snapshots and return notable_shifts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prior_as_of": {"type": "string"},
                "scope": {"type": "string", "enum": ["daily", "weekly"]},
                "current_as_of": {"type": "string"},
                "assets": _ASSET_FILTER_SCHEMA,
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
        "description": (
            "Evaluate allocation drift against multiple target/band scenarios."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "allocation_pct": {
                    "type": "object",
                    "properties": {
                        "BTC": {"type": "number"},
                        "ETH": {"type": "number"},
                        "CASH": {"type": "number"},
                    },
                    "required": ["BTC", "ETH", "CASH"],
                },
                "scenarios": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "target_pct": {
                                "type": "object",
                                "properties": {
                                    "BTC": {"type": "number"},
                                    "ETH": {"type": "number"},
                                    "CASH": {"type": "number"},
                                },
                            },
                            "band": {"type": "number"},
                        },
                        "required": ["target_pct"],
                    },
                },
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

_TOOL_NAMES = tuple(spec["tool_name"] for spec in _MCP_TOOLS)


def mcp_tool_specs() -> tuple[dict[str, Any], ...]:
    return _MCP_TOOLS


def public_mcp_url(*, base_url: str, mcp_path: str) -> str:
    return f"{base_url.rstrip('/')}{mcp_path}"


def resolve_public_base_url() -> str | None:
    for key in ("X402_PUBLIC_URL", "ALLOC_CONTEXT_MCP_PUBLIC_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value.rstrip("/")
    return None


def build_mcp_tool_extensions() -> dict[str, dict[str, Any]]:
    """Per-tool Bazaar MCP extensions keyed by tool name."""
    extensions: dict[str, dict[str, Any]] = {}
    for spec in _MCP_TOOLS:
        extensions[spec["tool_name"]] = declare_mcp_discovery_extension(
            DeclareMcpDiscoveryConfig(
                tool_name=spec["tool_name"],
                description=spec["description"],
                transport="streamable-http",
                input_schema=spec["input_schema"],
                example=spec["example"],
                output=OutputConfig(example=spec["output_example"]),
            )
        )
    return extensions


def build_http_route_extensions() -> dict[str, Any]:
    """Bazaar extension for the paid POST /mcp streamable HTTP endpoint."""
    primary = _MCP_TOOLS[0]
    return declare_discovery_extension(
        input={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": primary["tool_name"],
                "arguments": primary["example"],
            },
            "id": 1,
        },
        input_schema={
            "type": "object",
            "properties": {
                "jsonrpc": {"type": "string", "const": "2.0"},
                "method": {
                    "type": "string",
                    "description": "MCP JSON-RPC method (e.g. tools/call).",
                },
                "params": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": list(_TOOL_NAMES),
                            "description": (
                                "AllocContext tool: get_market_context, "
                                "get_context_bundle, get_rebalance_plan, "
                                "get_portfolio_state, check_allocation_band, "
                                "get_context_at, get_context_delta, or "
                                "check_allocation_bands."
                            ),
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Tool-specific arguments object.",
                        },
                    },
                    "required": ["name"],
                },
                "id": {"type": ["integer", "string"]},
            },
            "required": ["jsonrpc", "method", "params"],
        },
        body_type="json",
        output=OutputConfig(
            example={
                "jsonrpc": "2.0",
                "id": 1,
                "result": primary["output_example"],
            }
        ),
    )


def build_llms_txt(
    *,
    public_url: str,
    mcp_path: str,
    accepted_stables: tuple[str, ...] = ("USDC", "EURC"),
) -> str:
    endpoint = public_mcp_url(base_url=public_url, mcp_path=mcp_path)
    tool_lines = "\n".join(
        f"- `{spec['tool_name']}` — {spec['description']}" for spec in _MCP_TOOLS
    )
    return f"""# {SERVICE_TITLE}

{LISTING_DESCRIPTION}

## Paid MCP (x402, Base stablecoins)

- Endpoint: `{endpoint}`
- Transport: streamable HTTP (`POST {mcp_path}`)
- Health: `{public_url.rstrip('/')}/health` (free)
- Payment: x402 exact scheme on Base; payer picks one of
  **{", ".join(accepted_stables)}** (USD-pegged; bridge to Base first).
- Pricing: **$0.02** cached context/math; **$0.05** live ingest or live portfolio.

## Tools

{tool_lines}

## Search keywords

bitcoin, ethereum, btc, eth, portfolio allocation, allocation drift,
rebalance plan, rebalance btc eth, drift band, band check, market context,
fear and greed, sentiment, macro calendar, etf flows, agent tools, mcp, x402
"""


def build_well_known_x402(
    *,
    public_url: str,
    mcp_path: str,
    pay_to: str,
    price_light: str = "$0.02",
    price_heavy: str = "$0.05",
    network: str = "eip155:84532",
    accepted_stables: tuple[str, ...] = ("USDC", "EURC"),
) -> dict[str, Any]:
    endpoint = public_mcp_url(base_url=public_url, mcp_path=mcp_path)
    return {
        "name": SERVICE_NAME,
        "title": SERVICE_TITLE,
        "description": LISTING_DESCRIPTION,
        "tags": list(SERVICE_TAGS),
        "resources": [
            {
                "url": endpoint,
                "type": "http",
                "description": LISTING_DESCRIPTION,
                "tools": [
                    {
                        "name": spec["tool_name"],
                        "description": spec["description"],
                        "inputSchema": spec["input_schema"],
                    }
                    for spec in _MCP_TOOLS
                ],
            }
        ],
        "payment": {
            "scheme": "exact",
            "payTo": pay_to,
            "pricing": {
                "cached_context_and_math": price_light,
                "live_ingest_or_portfolio": price_heavy,
                "network": network,
                "assets": list(accepted_stables),
                "note": (
                    "Payer chooses one listed stable on Base; amounts are "
                    "USD-pegged per call tier."
                ),
            },
        },
    }
