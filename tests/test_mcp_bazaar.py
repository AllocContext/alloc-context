from __future__ import annotations

import pytest

from alloccontext.mcp.bazaar import (
    LISTING_DESCRIPTION,
    build_http_route_extensions,
    build_llms_txt,
    build_mcp_tool_extensions,
    build_well_known_x402,
    mcp_tool_specs,
)
from alloccontext.mcp.x402_config import MCP_HTTP_PATH, build_x402_routes, X402Settings


_EXPECTED_TOOLS = {
    "get_market_context",
    "get_context_bundle",
    "get_rebalance_plan",
    "get_portfolio_state",
    "check_allocation_band",
    "get_context_at",
    "get_context_delta",
    "check_allocation_bands",
}


def test_mcp_tool_specs_cover_all_tools() -> None:
    names = {spec["tool_name"] for spec in mcp_tool_specs()}
    assert names == _EXPECTED_TOOLS


def test_mcp_tool_bazaar_extensions() -> None:
    extensions = build_mcp_tool_extensions()
    assert set(extensions) == _EXPECTED_TOOLS
    for ext in extensions.values():
        bazaar = ext["bazaar"]
        assert bazaar["info"]["input"]["type"] == "mcp"
        assert bazaar["info"]["input"]["transport"] == "streamable-http"
        assert "inputSchema" in bazaar["info"]["input"]


def test_http_route_bazaar_extension_lists_tools() -> None:
    ext = build_http_route_extensions()["bazaar"]
    tool_enum = ext["info"]["input"]["body"]["params"]["name"]
    assert tool_enum == "get_market_context"
    schema_props = ext["schema"]["properties"]["input"]["properties"]["body"]["properties"]
    expected = [spec["tool_name"] for spec in mcp_tool_specs()]
    assert schema_props["params"]["properties"]["name"]["enum"] == expected


def test_x402_route_includes_bazaar_and_listing_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("X402_PUBLIC_URL", "https://mcp.example.com")
    settings = X402Settings(
        enabled=True,
        pay_to="0xSeller",
        facilitator_url="https://x402.org/facilitator",
        network="eip155:84532",
        mcp_price="$0.02",
        mcp_path=MCP_HTTP_PATH,
    )
    routes = build_x402_routes(settings)
    route = routes[f"POST {MCP_HTTP_PATH}"]
    assert route.resource == "https://mcp.example.com/mcp"
    assert route.description == LISTING_DESCRIPTION
    assert route.extensions is not None
    assert "bazaar" in route.extensions


def test_llms_txt_and_well_known() -> None:
    llms = build_llms_txt(
        public_url="https://mcp.example.com",
        mcp_path="/mcp",
    )
    assert "get_market_context" in llms
    assert "get_context_bundle" in llms
    assert "x402" in llms

    manifest = build_well_known_x402(
        public_url="https://mcp.example.com",
        mcp_path="/mcp",
        pay_to="0xSeller",
    )
    assert manifest["name"] == "AllocContext"
    assert len(manifest["resources"][0]["tools"]) == len(_EXPECTED_TOOLS)
    assert manifest["payment"]["pricing"]["cached_context_and_math"] == "$0.02"


def test_build_x402_resource_server_registers_bazaar(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("x402")
    from alloccontext.mcp.x402_config import build_x402_resource_server

    settings = X402Settings(
        enabled=True,
        pay_to="0xSeller",
        facilitator_url="https://x402.org/facilitator",
        network="eip155:84532",
        mcp_price="$0.02",
    )
    server = build_x402_resource_server(settings)
    assert server is not None
