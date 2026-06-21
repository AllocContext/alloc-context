from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from alloccontext.mcp.bridge import create_bridge_server
from alloccontext.mcp.upstream import call_upstream_tool
from alloccontext.user_config import UserConfig, load_user_config


def _portfolio_with_alts() -> dict:
    return {
        "available": True,
        "nav_usd": 10_000.0,
        "holdings": [
            {"symbol": "BTC", "qty": 0.5, "price_usd": 70_000.0, "value_usd": 35_000.0},
            {"symbol": "ETH", "qty": 2.0, "price_usd": 3_000.0, "value_usd": 6_000.0},
            {"symbol": "HYPE", "qty": 100.0, "price_usd": 25.0, "value_usd": 2_500.0},
            {"symbol": "USD", "qty": 500.0, "price_usd": 1.0, "value_usd": 500.0},
        ],
        "unrecognized": ["SOL"],
    }


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


@pytest.fixture
def payer_ready():
    with patch("alloccontext.mcp.bridge.bridge_upstream_ready", return_value=True):
        yield


def test_call_upstream_without_payer_returns_setup(bridge_user: UserConfig) -> None:
    result = call_upstream_tool(bridge_user, "get_market_context", {"scope": "daily"})
    assert result["available"] is False
    assert result["reason"] == "upstream_retired"


def test_call_upstream_without_payer_but_url_returns_payment_setup(
    tmp_path: Path,
) -> None:
    path = tmp_path / "user.yaml"
    path.write_text(
        """
upstream: https://mcp.example.com/mcp
exchanges:
  primary: kraken
  kraken:
    api_key: test-key
    api_secret: dGVzdA==
""",
        encoding="utf-8",
    )
    user = load_user_config(path)
    result = call_upstream_tool(user, "get_market_context", {"scope": "daily"})
    assert result["available"] is False
    assert result["reason"] == "upstream_payment_required"


def test_call_upstream_empty_url_returns_retired(
    bridge_user: UserConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVM_PRIVATE_KEY", "0x" + "11" * 32)
    result = call_upstream_tool(bridge_user, "get_market_context", {"scope": "daily"})
    assert result["available"] is False
    assert result["reason"] == "upstream_retired"


def test_create_bridge_server_registers_tools(bridge_user: UserConfig) -> None:
    pytest.importorskip("mcp")
    server = create_bridge_server(bridge_user)
    assert server is not None


def test_get_context_bundle_merges_portfolio(bridge_user: UserConfig, payer_ready) -> None:
    pytest.importorskip("mcp")
    upstream_bundle = {
        "scope": "daily",
        "market": {"available": True},
        "sentiment": {"available": True},
    }
    portfolio = {
        "available": True,
        "nav_usd": 100.0,
        "holdings": [{"symbol": "BTC"}],
    }

    server = create_bridge_server(bridge_user)
    captured: dict = {}
    with patch("alloccontext.mcp.bridge.call_upstream_tool") as upstream_mock:
        upstream_mock.side_effect = lambda _user, _name, args: (
            captured.update({"args": args}) or upstream_bundle
        )
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio", return_value=portfolio):
            tool_fn = server._tool_manager._tools["get_context_bundle"].fn  # type: ignore[attr-defined]
            result = tool_fn(scope="daily")
    assert captured["args"]["assets"] == ["BTC"]
    assert result["portfolio"] == portfolio
    assert result["market"]["available"] is True
    assert result["assets_scope"] == "portfolio"


def test_get_market_context_auto_scopes_assets(bridge_user: UserConfig, payer_ready) -> None:
    pytest.importorskip("mcp")
    portfolio = _portfolio_with_alts()
    server = create_bridge_server(bridge_user)
    captured: dict = {}

    def fake_upstream(_user, _name, args):
        captured["args"] = dict(args)
        return {"available": True, "market": {"available": True}, "assets": ["BTC", "ETH", "HYPE"]}

    with patch("alloccontext.mcp.bridge.call_upstream_tool", side_effect=fake_upstream):
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio", return_value=portfolio):
            tool_fn = server._tool_manager._tools["get_market_context"].fn  # type: ignore[attr-defined]
            result = tool_fn(scope="daily")

    assert captured["args"]["assets"] == ["BTC", "ETH", "HYPE", "SOL"]
    assert result["assets_omitted"] == ["SOL"]
    assert result["assets_scope"] == "portfolio"


def test_get_context_bundle_auto_scopes_assets(bridge_user: UserConfig, payer_ready) -> None:
    pytest.importorskip("mcp")
    portfolio = _portfolio_with_alts()
    server = create_bridge_server(bridge_user)
    captured: dict = {}

    def fake_upstream(_user, _name, args):
        captured["args"] = dict(args)
        return {
            "scope": "daily",
            "market": {"available": True},
            "assets_omitted": ["HYPE"],
        }

    with patch("alloccontext.mcp.bridge.call_upstream_tool", side_effect=fake_upstream):
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio", return_value=portfolio):
            tool_fn = server._tool_manager._tools["get_context_bundle"].fn  # type: ignore[attr-defined]
            result = tool_fn(scope="daily")

    assert captured["args"]["assets"] == ["BTC", "ETH", "HYPE", "SOL"]
    assert result["assets_omitted"] == ["HYPE", "SOL"]
    assert result["portfolio"] == portfolio
    assert result["assets_scope"] == "portfolio"


@pytest.mark.parametrize("tool_name", ["get_market_context", "get_context_bundle"])
def test_upstream_args_contain_symbols_only(
    bridge_user: UserConfig,
    payer_ready,
    tool_name: str,
) -> None:
    pytest.importorskip("mcp")
    portfolio = _portfolio_with_alts()
    server = create_bridge_server(bridge_user)
    captured: dict = {}

    def fake_upstream(_user, _name, args):
        captured["args"] = dict(args)
        return {"available": True, "market": {"available": True}, "scope": "daily"}

    with patch("alloccontext.mcp.bridge.call_upstream_tool", side_effect=fake_upstream):
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio", return_value=portfolio):
            tool_fn = server._tool_manager._tools[tool_name].fn  # type: ignore[attr-defined]
            tool_fn(scope="daily", freshness="cached")

    args = captured["args"]
    assert set(args.keys()) == {"scope", "freshness", "assets"}
    assert args["scope"] == "daily"
    assert args["freshness"] == "cached"
    assert args["assets"] == ["BTC", "ETH", "HYPE", "SOL"]
    assert "holdings" not in args
    assert "nav_usd" not in args
    assert "qty" not in args


def test_explicit_assets_skip_portfolio_auto_scope(bridge_user: UserConfig, payer_ready) -> None:
    pytest.importorskip("mcp")
    server = create_bridge_server(bridge_user)
    captured: dict = {}

    def fake_upstream(_user, _name, args):
        captured["args"] = dict(args)
        return {"available": True, "market": {"available": True}}

    with patch("alloccontext.mcp.bridge.call_upstream_tool", side_effect=fake_upstream):
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio") as fetch_mock:
            tool_fn = server._tool_manager._tools["get_market_context"].fn  # type: ignore[attr-defined]
            result = tool_fn(scope="daily", assets=["BTC"])

    fetch_mock.assert_not_called()
    assert captured["args"]["assets"] == ["BTC"]
    assert result["assets_scope"] == "explicit"


def test_get_context_bundle_skips_portfolio_fetch_without_payer(bridge_user: UserConfig) -> None:
    pytest.importorskip("mcp")
    server = create_bridge_server(bridge_user)
    with patch("alloccontext.mcp.bridge.call_upstream_tool") as upstream_mock:
        upstream_mock.return_value = {
            "available": False,
            "reason": "upstream_payment_required",
        }
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio") as fetch_mock:
            tool_fn = server._tool_manager._tools["get_context_bundle"].fn  # type: ignore[attr-defined]
            result = tool_fn(scope="daily")
    fetch_mock.assert_not_called()
    assert result["reason"] == "upstream_payment_required"


def test_get_context_bundle_theses_without_payer_fails_closed(
    bridge_user: UserConfig,
) -> None:
    pytest.importorskip("mcp")
    server = create_bridge_server(bridge_user)
    with patch("alloccontext.mcp.bridge.call_upstream_tool") as upstream_mock:
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio") as fetch_mock:
            tool_fn = server._tool_manager._tools["get_context_bundle"].fn  # type: ignore[attr-defined]
            result = tool_fn(
                scope="daily",
                theses=[
                    {
                        "id": "t1",
                        "recorded_at": "2026-06-01T00:00:00Z",
                        "claims": [
                            {"type": "MARKET_SENTIMENT", "direction": "IMPROVING"}
                        ],
                    }
                ],
            )
    upstream_mock.assert_not_called()
    fetch_mock.assert_not_called()
    assert result["reason"] == "upstream_payment_required"


def test_get_market_context_skips_portfolio_fetch_without_payer(bridge_user: UserConfig) -> None:
    pytest.importorskip("mcp")
    server = create_bridge_server(bridge_user)
    with patch("alloccontext.mcp.bridge.call_upstream_tool") as upstream_mock:
        upstream_mock.return_value = {
            "available": False,
            "reason": "upstream_payment_required",
        }
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio") as fetch_mock:
            tool_fn = server._tool_manager._tools["get_market_context"].fn  # type: ignore[attr-defined]
            result = tool_fn(scope="daily")
    fetch_mock.assert_not_called()
    assert result["reason"] == "upstream_payment_required"


def test_get_market_context_portfolio_unavailable_scope(bridge_user: UserConfig, payer_ready) -> None:
    pytest.importorskip("mcp")
    server = create_bridge_server(bridge_user)
    portfolio = {"available": False, "reason": "portfolio_fetch_failed"}

    def fake_upstream(_user, _name, args):
        assert args["assets"] is None
        return {"available": True, "market": {"available": True}}

    with patch("alloccontext.mcp.bridge.call_upstream_tool", side_effect=fake_upstream):
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio", return_value=portfolio):
            tool_fn = server._tool_manager._tools["get_market_context"].fn  # type: ignore[attr-defined]
            result = tool_fn(scope="daily")

    assert result["assets_scope"] == "portfolio_unavailable"


def test_empty_assets_list_triggers_auto_scope(bridge_user: UserConfig, payer_ready) -> None:
    pytest.importorskip("mcp")
    portfolio = _portfolio_with_alts()
    server = create_bridge_server(bridge_user)
    captured: dict = {}

    def fake_upstream(_user, _name, args):
        captured["args"] = dict(args)
        return {"available": True, "market": {"available": True}}

    with patch("alloccontext.mcp.bridge.call_upstream_tool", side_effect=fake_upstream):
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio", return_value=portfolio):
            tool_fn = server._tool_manager._tools["get_market_context"].fn  # type: ignore[attr-defined]
            tool_fn(scope="daily", assets=[])

    assert captured["args"]["assets"] == ["BTC", "ETH", "HYPE", "SOL"]


def test_no_exchange_keys_use_default_scope(bridge_user: UserConfig, payer_ready) -> None:
    pytest.importorskip("mcp")
    user = UserConfig.empty()
    server = create_bridge_server(user)
    captured: dict = {}

    def fake_upstream(_user, _name, args):
        captured["args"] = dict(args)
        return {"available": True, "market": {"available": True}}

    with patch("alloccontext.mcp.bridge.call_upstream_tool", side_effect=fake_upstream):
        with patch("alloccontext.mcp.bridge.fetch_user_portfolio") as fetch_mock:
            tool_fn = server._tool_manager._tools["get_market_context"].fn  # type: ignore[attr-defined]
            result = tool_fn(scope="daily")

    fetch_mock.assert_not_called()
    assert captured["args"]["assets"] is None
    assert result["assets_scope"] == "default"
