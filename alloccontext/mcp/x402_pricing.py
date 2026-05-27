from __future__ import annotations

from typing import Any

from x402.http.types import HTTPRequestContext

DEFAULT_MCP_PRICE_HEAVY = "$0.05"

HEAVY_MCP_TOOLS = frozenset({"get_portfolio_state"})


def mcp_call_is_heavy(body: dict[str, Any] | None) -> bool:
    """Return True when an MCP tools/call warrants the heavy x402 price."""
    if not body or body.get("method") != "tools/call":
        return False

    params = body.get("params")
    if not isinstance(params, dict):
        return False

    tool_name = params.get("name")
    if isinstance(tool_name, str) and tool_name in HEAVY_MCP_TOOLS:
        return True

    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        return False

    freshness = arguments.get("freshness")
    return isinstance(freshness, str) and freshness.strip().lower() == "live"


async def _read_request_json(context: HTTPRequestContext) -> dict[str, Any] | None:
    request = getattr(context.adapter, "_request", None)
    if request is None:
        return None
    try:
        body = await request.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


def build_mcp_dynamic_price(*, light_price: str, heavy_price: str):
    """Build an async x402 DynamicPrice callback for POST /mcp."""

    async def resolve_price(context: HTTPRequestContext) -> str:
        body = await _read_request_json(context)
        if mcp_call_is_heavy(body):
            return heavy_price
        return light_price

    return resolve_price
