from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from alloccontext.config import load_config
from alloccontext.ingest.wallet.alchemy import (
    AlchemyClient,
    AlchemyTokenRow,
    _parse_hex_balance,
)
from alloccontext.ingest.wallet.portfolio import fetch_wallet_portfolio_snapshot
from pathlib import Path


VITALIK = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


class _FakeAlchemy(AlchemyClient):
    def __init__(self) -> None:
        pass

    def token_balances(self, address: str, chain_ids: tuple[int, ...]) -> list[AlchemyTokenRow]:
        return [
            AlchemyTokenRow(symbol="ETH", quantity=2.0, price_usd=3000.0, is_native=True),
            AlchemyTokenRow(symbol="USDC", quantity=500.0, price_usd=1.0),
            AlchemyTokenRow(symbol="SHIB", quantity=1_000_000.0, price_usd=0.0),
        ]


def test_parse_hex_balance() -> None:
    assert _parse_hex_balance("0x3b9aca00", 6) == 1000.0


def test_fetch_wallet_alchemy_provider(config, monkeypatch) -> None:
    monkeypatch.setenv("ALCHEMY_API_KEY", "test-key")
    with patch(
        "alloccontext.ingest.wallet.portfolio.resolve_balance_prices",
        return_value={"ETH": 3000.0, "USDC": 1.0, "SHIB": 0.0},
    ):
        snap = fetch_wallet_portfolio_snapshot(
            VITALIK,
            config,
            alchemy_client=_FakeAlchemy(),
        )
    assert snap.nav_usd > 0
    symbols = {row["symbol"] for row in snap.holdings}
    assert "ETH" in symbols
    assert "USD" in symbols
    assert "SHIB" not in symbols


def test_alchemy_post_parses_response() -> None:
    client = AlchemyClient("test-key", max_retries=0)
    payload = {
        "data": {
            "tokens": [
                {
                    "network": "eth-mainnet",
                    "tokenAddress": None,
                    "tokenBalance": "0xde0b6b3a7640000",
                    "tokenMetadata": {"symbol": None, "decimals": None},
                    "tokenPrices": [{"currency": "usd", "value": "3000"}],
                }
            ],
            "pageKey": None,
        }
    }
    with patch("alloccontext.ingest.wallet.alchemy.requests.post") as post:
        post.return_value = MagicMock(
            status_code=200,
            json=lambda: payload,
            raise_for_status=lambda: None,
        )
        rows = client.token_balances(VITALIK, (1,))
    assert len(rows) == 1
    assert rows[0].symbol == "ETH"
    assert rows[0].quantity == 1.0


def test_wallet_provider_etherscan_config(tmp_path, monkeypatch) -> None:
    from alloccontext.ingest.wallet.portfolio import WalletPortfolioError

    db = tmp_path / "test.db"
    cfg_path = tmp_path / "config.yaml"
    example = Path("config/config.example.yaml").read_text()
    cfg_path.write_text(
        example.replace("state/alloccontext.db", str(db)).replace(
            "provider: alchemy",
            "provider: etherscan",
        )
    )
    cfg = load_config(cfg_path)
    assert cfg.wallet.provider == "etherscan"
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    with pytest.raises(WalletPortfolioError, match="missing_etherscan_api_key"):
        fetch_wallet_portfolio_snapshot(VITALIK, cfg, etherscan_client=MagicMock())
