from __future__ import annotations

from unittest.mock import patch

import pytest

from alloccontext.integrations.langchain import (
    DEFAULT_HOSTED_TOOLS,
    build_hosted_langchain_tools,
    hosted_user_config,
    official_hosted_mcp_url,
)
from alloccontext.user_config import DEFAULT_UPSTREAM_URL


def test_official_hosted_mcp_url() -> None:
    assert official_hosted_mcp_url().startswith("https://")


def test_hosted_user_config_uses_upstream() -> None:
    user = hosted_user_config()
    assert user.uses_upstream() is True
    assert user.upstream == DEFAULT_UPSTREAM_URL


def test_build_hosted_langchain_tools_invokes_upstream() -> None:
    pytest.importorskip("langchain_core")

    user = hosted_user_config()
    sample = {"as_of": "2026-05-28T12:00:00+00:00", "freshness": "cached"}
    with patch(
        "alloccontext.integrations.langchain.call_upstream_tool",
        return_value=sample,
    ) as upstream_mock:
        tools = build_hosted_langchain_tools(
            user=user,
            tool_names=("get_market_context",),
        )
        assert len(tools) == 1
        assert tools[0].name == "get_market_context"
        raw = tools[0].invoke(
            {"scope": "daily", "freshness": "cached", "assets": ["BTC", "ETH"]}
        )
        upstream_mock.assert_called_once_with(
            user,
            "get_market_context",
            {"scope": "daily", "freshness": "cached", "assets": ["BTC", "ETH"]},
        )
    import json

    assert json.loads(raw) == sample


def test_build_hosted_langchain_tools_default_set() -> None:
    pytest.importorskip("langchain_core")
    tools = build_hosted_langchain_tools(user=hosted_user_config())
    assert tuple(tool.name for tool in tools) == DEFAULT_HOSTED_TOOLS


def test_build_hosted_langchain_tools_unknown_name() -> None:
    pytest.importorskip("langchain_core")
    with pytest.raises(ValueError, match="Unknown MCP tool"):
        build_hosted_langchain_tools(
            user=hosted_user_config(),
            tool_names=("not_a_tool",),
        )


def test_build_hosted_langchain_tools_requires_langchain_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "langchain_core.tools":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match="langchain-core"):
        build_hosted_langchain_tools(user=hosted_user_config())
