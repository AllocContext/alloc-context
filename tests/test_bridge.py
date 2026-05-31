from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from alloccontext.mcp.bridge import create_bridge_server
from alloccontext.mcp.upstream import call_upstream_tool
from alloccontext.user_config import UserConfig, load_user_config


@pytest.fixture
def bridge_user(tmp_path: Path) -> UserConfig:
    path = tmp_path / "user.yaml"
    path.write_text(
        """
exchanges:
  primary: kraken
  kraken:
    api_key: test-key
    api_secret: dGVzdA==
""",
        encoding="utf-8",
    )
    return load_user_config(path)


def test_call_upstream_without_payer_returns_setup(bridge_user: UserConfig) -> None:
    result = call_upstream_tool(bridge_user, "get_market_context", {"scope": "daily"})
    assert result["available"] is False
    assert result["reason"] == "upstream_payment_required"


def test_create_bridge_server_registers_tools(bridge_user: UserConfig) -> None:
    pytest.importorskip("mcp")
    server = create_bridge_server(bridge_user)
    assert server is not None


def test_get_context_bundle_merges_portfolio(bridge_user: UserConfig) -> None:
    pytest.importorskip("mcp")
    upstream_bundle = {
        "scope": "daily",
        "market": {"available": True},
        "sentiment": {"available": True},
    }
    portfolio = {"available": True, "nav_usd": 100.0}

    server = create_bridge_server(bridge_user)
    with patch("alloccontext.mcp.bridge.call_upstream_tool", return_value=upstream_bundle):
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio", return_value=portfolio):
            tool_fn = server._tool_manager._tools["get_context_bundle"].fn  # type: ignore[attr-defined]
            result = tool_fn(scope="daily")
    assert result["portfolio"] == portfolio
    assert result["market"]["available"] is True
