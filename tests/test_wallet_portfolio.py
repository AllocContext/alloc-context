from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from alloccontext.ingest.wallet.chains import DEFAULT_WALLET_CHAIN_IDS
from alloccontext.ingest.wallet.etherscan import EtherscanClient, TokenBalanceRow
from alloccontext.ingest.wallet.portfolio import (
    fetch_wallet_portfolio_snapshot,
    normalize_wallet_symbol,
    validate_wallet_address,
)
from alloccontext.mcp.handlers import get_portfolio_state


VITALIK = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


class _FakeEtherscan(EtherscanClient):
    def __init__(self) -> None:
        pass

    def native_balance_eth(self, chain_id: int, address: str) -> float:
        if chain_id == 1:
            return 1.5
        if chain_id == 42161:
            return 0.25
        return 0.0

    def curated_token_balances(self, chain_id: int, address: str) -> list[TokenBalanceRow]:
        if chain_id == 1:
            return [
                TokenBalanceRow(symbol="USDC", quantity=1000.0),
                TokenBalanceRow(symbol="WETH", quantity=0.5),
                TokenBalanceRow(symbol="SHIB", quantity=1.0),
            ]
        if chain_id == 8453:
            return [TokenBalanceRow(symbol="WBTC", quantity=0.01)]
        return []


def test_validate_wallet_address_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="invalid_wallet_address"):
        validate_wallet_address("not-an-address")


def test_normalize_wallet_symbol_maps_wrapped_assets() -> None:
    assert normalize_wallet_symbol("weth") == "ETH"
    assert normalize_wallet_symbol("WBTC") == "BTC"


def test_fetch_wallet_portfolio_snapshot_aggregates_multichain(config, monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    with patch(
        "alloccontext.ingest.wallet.portfolio.resolve_balance_prices",
        return_value={"ETH": 3000.0, "BTC": 70000.0, "SHIB": 0.0},
    ):
        snap = fetch_wallet_portfolio_snapshot(
            VITALIK,
            config,
            client=_FakeEtherscan(),
        )
    assert snap.nav_usd > 0
    symbols = {row["symbol"] for row in snap.holdings}
    assert "ETH" in symbols
    assert "BTC" in symbols
    assert "USD" in symbols
    assert snap.cash_usd == 1000.0
    assert "SHIB" not in symbols


def test_get_portfolio_state_wallet_live(config, monkeypatch) -> None:
    from alloccontext.ingest.kraken_portfolio import PortfolioSnapshot

    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    snap = PortfolioSnapshot(
        ts="2026-06-06T12:00:00+00:00",
        nav_usd=5000.0,
        cash_usd=0.0,
        btc_usd=0.0,
        eth_usd=5000.0,
        btc_pct=0.0,
        eth_pct=1.0,
        cash_pct=0.0,
        prices={"ETH": 3000.0},
        holdings=[],
    )
    with patch(
        "alloccontext.mcp.handlers.fetch_live_portfolio_snapshot",
        return_value=snap,
    ):
        result = get_portfolio_state(
            config,
            exchange="wallet",
            wallet_address=VITALIK,
        )
    assert result["available"] is True
    assert result["exchange"] == "wallet"
    assert result["wallet_address"] == VITALIK


def test_get_portfolio_state_wallet_requires_address(config) -> None:
    result = get_portfolio_state(config, exchange="wallet")
    assert result["available"] is False
    assert result["reason"] == "wallet_address is required"


def test_wallet_config_defaults(config) -> None:
    assert config.wallet.enabled is True
    assert config.wallet.chain_ids == DEFAULT_WALLET_CHAIN_IDS
    assert config.wallet.min_value_usd == 1.0


def test_fetch_wallet_missing_api_key(config, monkeypatch) -> None:
    from alloccontext.ingest.wallet.portfolio import WalletPortfolioError

    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    with pytest.raises(WalletPortfolioError, match="missing_etherscan_api_key"):
        fetch_wallet_portfolio_snapshot(VITALIK, config, client=MagicMock())
