from __future__ import annotations

import pytest

from alloccontext.mcp.bazaar import build_mcp_server_card, mcp_tool_specs
from alloccontext.mcp.tool_catalog import (
    MCP_SERVER_PROMPTS,
    MCP_SERVER_RESOURCES,
    assert_input_schema_descriptions,
    tool_annotations,
)


def test_bazaar_tool_input_schemas_have_descriptions() -> None:
    for spec in mcp_tool_specs():
        assert_input_schema_descriptions(
            spec["input_schema"],
            tool_name=spec["tool_name"],
        )


def test_server_card_tools_include_smithery_metadata() -> None:
    card = build_mcp_server_card(version="0.2.1")
    assert len(card["tools"]) == 8
    for tool in card["tools"]:
        assert tool.get("title")
        assert tool.get("description")
        assert tool.get("inputSchema")
        assert tool.get("outputSchema")
        annotations = tool.get("annotations") or {}
        assert annotations.get("readOnlyHint") is True
        assert annotations.get("destructiveHint") is False
        assert "idempotentHint" in annotations
        assert "openWorldHint" in annotations


def test_server_card_includes_prompts_and_resources() -> None:
    card = build_mcp_server_card(version="0.2.1")
    assert len(card["prompts"]) == len(MCP_SERVER_PROMPTS) >= 3
    assert len(card["resources"]) == len(MCP_SERVER_RESOURCES) >= 1


def test_portfolio_tool_is_open_world() -> None:
    hints = tool_annotations("get_portfolio_state")
    assert hints["openWorldHint"] is True


def test_mcp_server_tools_expose_titles_and_annotations() -> None:
    pytest.importorskip("mcp")
    import asyncio

    from alloccontext.mcp.server import create_server
    from alloccontext.mcp.tool_catalog import tool_title

    async def _check() -> None:
        server = create_server()
        tools = await server.list_tools()
        assert len(tools) == 8
        for tool in tools:
            assert tool.title == tool_title(tool.name)
            assert tool.annotations is not None
            assert tool.annotations.readOnlyHint is True
            assert tool.annotations.destructiveHint is False

    asyncio.run(_check())
