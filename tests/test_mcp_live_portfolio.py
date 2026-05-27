from __future__ import annotations

from unittest.mock import patch

from alloccontext.ingest.kraken_portfolio import PortfolioSnapshot
from alloccontext.mcp.handlers import get_portfolio_state, get_rebalance_plan


def test_get_rebalance_plan_coinbase_exchange() -> None:
    result = get_rebalance_plan(
        {"BTC": 0.613, "ETH": 0.163, "CASH": 0.224},
        {"BTC": 0.65, "ETH": 0.20, "CASH": 0.15},
        1000.0,
        exchange="coinbase",
    )
    assert result["exchange"] == "coinbase"
    assert any("BTC-USD" in line for line in result["moves"])


def test_get_portfolio_state_live(config) -> None:
    snap = PortfolioSnapshot(
        ts="2026-05-27T12:00:00+00:00",
        nav_usd=1000.0,
        cash_usd=100.0,
        btc_usd=700.0,
        eth_usd=200.0,
        btc_pct=0.7,
        eth_pct=0.2,
        cash_pct=0.1,
        prices={"BTC": 70000.0, "ETH": 3000.0},
    )
    with patch(
        "alloccontext.mcp.handlers.fetch_live_portfolio_snapshot",
        return_value=snap,
    ):
        result = get_portfolio_state(
            config,
            exchange="kraken",
            api_key="test-key",
            api_secret="test-secret",
        )
    assert result["available"] is True
    assert result["exchange"] == "kraken"
    assert result["source"] == "live"
    assert result["nav_usd"] == 1000.0
    assert "as_of" in result
    assert result["allocation_pct"]["BTC"] == 0.7


def test_get_portfolio_state_api_error(config) -> None:
    from alloccontext.ingest.exchange.live import LivePortfolioError

    with patch(
        "alloccontext.mcp.handlers.fetch_live_portfolio_snapshot",
        side_effect=LivePortfolioError("invalid_key"),
    ):
        result = get_portfolio_state(
            config,
            exchange="coinbase",
            api_key="bad",
            api_secret="bad",
        )
    assert result["available"] is False
    assert result["reason"] == "invalid_key"
