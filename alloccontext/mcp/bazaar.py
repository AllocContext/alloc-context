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
SERVICE_TAGS = ("btc", "eth", "rebalance", "allocation", "crypto")

LISTING_DESCRIPTION = (
    "Deterministic BTC/ETH allocation facts for agents: fused market context "
    "(sentiment, macro, ETF flows, breadth), USD rebalance move lines, and "
    "allocation band drift checks. No LLM — structured JSON only."
)

_MCP_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "tool_name": "get_market_context",
        "description": (
            "Fused market backdrop for BTC/ETH allocation: Fear & Greed, Kalshi "
            "sentiment, macro calendar, FRED indicators, ETF flows, and breadth. "
            "Use freshness=cached for hosted cache or freshness=live to refresh."
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
                        "(requires operator API keys on the host)."
                    ),
                },
            },
        },
        "example": {"scope": "daily", "freshness": "cached"},
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
        "tool_name": "get_rebalance_plan",
        "description": (
            "Compute USD deltas and exchange-style move lines to reach a target "
            "BTC/ETH/CASH split from current allocation and NAV. Pure math."
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
            },
            "required": ["allocation_pct", "target_pct", "nav_usd"],
        },
        "example": {
            "allocation_pct": {"BTC": 0.45, "ETH": 0.45, "CASH": 0.10},
            "target_pct": {"BTC": 0.50, "ETH": 0.40, "CASH": 0.10},
            "nav_usd": 10000,
        },
        "output_example": {
            "as_of": "2026-05-21T12:00:00+00:00",
            "age_seconds": 0,
            "moves": [],
            "deltas_usd": {"BTC": 500.0, "ETH": -500.0, "CASH": 0.0},
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
                                "Tier 1 AllocContext tool: get_market_context, "
                                "get_rebalance_plan, or check_allocation_band."
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


def build_llms_txt(*, public_url: str, mcp_path: str) -> str:
    endpoint = public_mcp_url(base_url=public_url, mcp_path=mcp_path)
    tool_lines = "\n".join(
        f"- `{spec['tool_name']}` — {spec['description']}" for spec in _MCP_TOOLS
    )
    return f"""# {SERVICE_TITLE}

{LISTING_DESCRIPTION}

## Paid MCP (x402, USDC on Base)

- Endpoint: `{endpoint}`
- Transport: streamable HTTP (`POST {mcp_path}`)
- Health: `{public_url.rstrip('/')}/health` (free)
- Payment: x402 exact scheme; unpaid calls return 402 Payment Required.

## Tools

{tool_lines}

## Search keywords

bitcoin, ethereum, btc, eth, portfolio allocation, rebalance, drift, band,
market context, sentiment, macro, etf flows, agent tools, mcp, x402
"""


def build_well_known_x402(*, public_url: str, mcp_path: str, pay_to: str) -> dict[str, Any]:
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
        },
    }
