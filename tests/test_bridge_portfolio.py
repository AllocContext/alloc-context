from __future__ import annotations

from pathlib import Path

from alloccontext.mcp.bridge_portfolio import (
    UPSTREAM_CONTEXT_ARG_KEYS,
    build_upstream_context_args,
    default_bridge_app_config,
    market_symbols_from_portfolio,
    merge_assets_omitted,
    resolve_bridge_assets,
)
from alloccontext.user_config import load_user_config


def _user_with_keys(path: Path):
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


def test_market_symbols_from_portfolio_excludes_stables() -> None:
    portfolio = {
        "available": True,
        "holdings": [
            {"symbol": "BTC", "qty": 1.0},
            {"symbol": "ETH", "qty": 2.0},
            {"symbol": "HYPE", "qty": 10.0},
            {"symbol": "USD", "qty": 100.0},
            {"symbol": "USDC", "qty": 50.0},
        ],
        "unrecognized": ["SOL"],
    }
    assert market_symbols_from_portfolio(portfolio) == ["BTC", "ETH", "HYPE", "SOL"]


def test_market_symbols_from_portfolio_unavailable() -> None:
    assert market_symbols_from_portfolio({"available": False}) == []


def test_merge_assets_omitted_combines_upstream_and_unrecognized() -> None:
    payload = {"market": {"available": True}, "assets_omitted": ["HYPE"]}
    portfolio = {"available": True, "unrecognized": ["SOL", "HYPE"]}
    merged = merge_assets_omitted(payload, portfolio)
    assert merged["assets_omitted"] == ["HYPE", "SOL"]


def test_merge_assets_omitted_clears_when_empty() -> None:
    payload = {"market": {"available": True}, "assets_omitted": []}
    portfolio = {"available": True, "unrecognized": []}
    merged = merge_assets_omitted(payload, portfolio)
    assert "assets_omitted" not in merged


def test_build_upstream_context_args_allowlist() -> None:
    args = build_upstream_context_args(
        scope="daily",
        freshness="cached",
        assets=["BTC", "HYPE"],
    )
    assert set(args.keys()) == UPSTREAM_CONTEXT_ARG_KEYS
    assert args["assets"] == ["BTC", "HYPE"]


def test_resolve_bridge_assets_explicit(tmp_path: Path) -> None:
    user = _user_with_keys(tmp_path / "user.yaml")
    config = default_bridge_app_config()
    assets, scope = resolve_bridge_assets(user, config, ["BTC"], portfolio=None)
    assert assets == ["BTC"]
    assert scope == "explicit"


def test_resolve_bridge_assets_portfolio_unavailable(tmp_path: Path) -> None:
    user = _user_with_keys(tmp_path / "user.yaml")
    config = default_bridge_app_config()
    portfolio = {"available": False, "reason": "portfolio_fetch_failed"}
    assets, scope = resolve_bridge_assets(user, config, None, portfolio=portfolio)
    assert assets is None
    assert scope == "portfolio_unavailable"


def test_resolve_bridge_assets_from_holdings(tmp_path: Path) -> None:
    user = _user_with_keys(tmp_path / "user.yaml")
    config = default_bridge_app_config()
    portfolio = {
        "available": True,
        "holdings": [{"symbol": "BTC"}, {"symbol": "HYPE"}],
    }
    assets, scope = resolve_bridge_assets(user, config, None, portfolio=portfolio)
    assert assets == ["BTC", "HYPE"]
    assert scope == "portfolio"
