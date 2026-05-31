from __future__ import annotations

import pytest

from alloccontext.mcp.bazaar import (
    LISTING_DESCRIPTION,
    build_http_route_extensions,
    build_llms_txt,
    build_mcp_server_card,
    build_mcp_tool_extensions,
    build_well_known_x402,
    mcp_tool_specs,
    smoke_tool_arguments,
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


def test_smoke_tool_arguments_use_bazaar_examples() -> None:
    args = smoke_tool_arguments("get_rebalance_plan")
    assert "allocation_pct" in args
    assert "nav_usd" in args
    args = smoke_tool_arguments("get_context_at")
    assert args["match"] == "at_or_before"
    assert "as_of" in args
    delta_args = smoke_tool_arguments("get_context_delta")
    assert delta_args["scope"] == "daily"
    assert "prior_as_of" in delta_args
    assert "2020" not in delta_args["prior_as_of"]


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
    from alloccontext.mcp.bazaar import LICENSE_MARKERS, PRIVACY_PILLAR_MARKERS

    llms = build_llms_txt(
        public_url="https://mcp.example.com",
        mcp_path="/mcp",
    )
    assert "get_market_context" in llms
    assert "get_context_bundle" in llms
    assert "x402" in llms
    assert "examples.md" in llms
    assert "## Privacy" in llms
    assert "## License" in llms
    llms_lower = llms.lower()
    for marker in PRIVACY_PILLAR_MARKERS:
        assert marker in llms_lower
    for marker in LICENSE_MARKERS:
        assert marker in llms_lower

    manifest = build_well_known_x402(
        public_url="https://mcp.example.com",
        mcp_path="/mcp",
        pay_to="0xSeller",
    )
    assert manifest["name"] == "AllocContext"
    assert len(manifest["resources"][0]["tools"]) == len(_EXPECTED_TOOLS)
    assert manifest["payment"]["pricing"]["cached_context_and_math"] == "$0.02"
    assert manifest["payment"]["pricing"]["network"] == "eip155:84532"
    assert manifest["payment"]["pricing"]["assets"] == ["USDC", "EURC"]


def test_build_well_known_x402_honors_network() -> None:
    manifest = build_well_known_x402(
        public_url="https://mcp.example.com",
        mcp_path="/mcp",
        pay_to="0xSeller",
        network="eip155:8453",
    )
    assert manifest["payment"]["pricing"]["network"] == "eip155:8453"


def test_build_mcp_server_card_lists_tools() -> None:
    card = build_mcp_server_card(version="0.2.0")
    assert card["serverInfo"]["version"] == "0.2.0"
    assert card["authentication"]["required"] is True
    names = {tool["name"] for tool in card["tools"]}
    assert names == _EXPECTED_TOOLS


def test_mcp_server_card_route(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from alloccontext.mcp.http import build_http_app

    monkeypatch.setenv("ALLOC_CONTEXT_CONFIG", "config/config.example.yaml")
    monkeypatch.setenv("X402_PUBLIC_URL", "https://mcp.example.com")
    app = build_http_app(x402=False, config_path="config/config.example.yaml")

    with TestClient(app) as client:
        resp = client.get("/.well-known/mcp/server-card.json")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["tools"]) == len(_EXPECTED_TOOLS)
    assert body["authentication"]["required"] is True


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
