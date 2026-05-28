from __future__ import annotations

import pytest

from alloccontext.mcp.bazaar import (
    BAZAAR_INDEX_TAGS,
    BAZAAR_SERVICE_NAME,
    DISCOVERY_KEYWORD_MARKERS,
    LISTING_DESCRIPTION,
    build_mcp_tool_extensions,
)
from alloccontext.mcp.x402_bazaar_dynamic import (
    AllocContextHTTPResourceServer,
    mcp_tool_name_from_body,
    patch_resource_info_for_bazaar,
)


def test_bazaar_service_name_within_cdp_limit() -> None:
    assert len(BAZAAR_SERVICE_NAME) <= 32


def test_bazaar_index_tags_within_cdp_limit() -> None:
    assert len(BAZAAR_INDEX_TAGS) <= 5
    assert all(len(tag) <= 32 for tag in BAZAAR_INDEX_TAGS)


def test_listing_description_includes_search_phrases() -> None:
    lowered = LISTING_DESCRIPTION.lower()
    for phrase in ("allocation drift", "rebalance", "fear & greed", "etf flows"):
        assert phrase in lowered


def test_mcp_tool_name_from_body() -> None:
    body = {
        "method": "tools/call",
        "params": {"name": "get_rebalance_plan", "arguments": {}},
    }
    assert mcp_tool_name_from_body(body) == "get_rebalance_plan"
    assert mcp_tool_name_from_body({"method": "initialize"}) is None


def test_resource_info_patch_adds_bazaar_metadata() -> None:
    patch_resource_info_for_bazaar()
    from x402.schemas.payments import ResourceInfo

    info = ResourceInfo(url="https://mcp.example.com/mcp", description="test")
    assert info.service_name == BAZAAR_SERVICE_NAME
    assert info.tags == list(BAZAAR_INDEX_TAGS)


def test_alloc_http_server_selects_tool_bazaar_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("x402")
    from alloccontext.mcp.x402_bazaar_dynamic import _mcp_tool_ctx
    from alloccontext.mcp.x402_config import MCP_HTTP_PATH, build_x402_routes, X402Settings
    from x402.http import FacilitatorConfig, HTTPFacilitatorClient
    from x402.server import x402ResourceServer

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
    server = x402ResourceServer(HTTPFacilitatorClient(FacilitatorConfig(url="https://x402.org/facilitator")))
    http_server = AllocContextHTTPResourceServer(server, routes)

    class _Adapter:
        def get_url(self) -> str:
            return "https://mcp.example.com/mcp"

    token = _mcp_tool_ctx.set("get_rebalance_plan")
    try:
        match = http_server._get_route_config("/mcp", "POST")
    finally:
        _mcp_tool_ctx.reset(token)

    assert match is not None
    route_config, _pattern = match
    tool_ext = build_mcp_tool_extensions()["get_rebalance_plan"]
    assert route_config.extensions == tool_ext
    assert "rebalance" in (route_config.description or "").lower()


def test_discovery_keyword_markers_in_llms_txt() -> None:
    from alloccontext.mcp.bazaar import build_llms_txt

    llms = build_llms_txt(public_url="https://mcp.example.com", mcp_path="/mcp")
    lowered = llms.lower()
    for marker in DISCOVERY_KEYWORD_MARKERS:
        assert marker in lowered
