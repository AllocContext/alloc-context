from __future__ import annotations

from alloccontext.mcp.bridge_portfolio import (
    market_symbols_from_portfolio,
    merge_assets_omitted,
)


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
