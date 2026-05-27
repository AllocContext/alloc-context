from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from alloccontext.ingest.coinbase_client import (
    normalize_coinbase_balances,
    normalize_pem_secret,
    product_to_symbol,
)
from alloccontext.ingest.coinbase_portfolio import (
    fetch_portfolio_snapshot,
    refresh_coinbase,
)
from alloccontext.ingest.kraken_portfolio import PortfolioSnapshot


class FakeCoinbaseClient:
    def get_ticker(self, product_id: str) -> dict[str, float]:
        return {"last": 100_000.0 if product_id.startswith("BTC") else 3_000.0}

    def get_ohlc(self, product_id: str, interval_minutes: int = 1440) -> list[dict[str, float]]:
        recent = float(int(time.time()) - 86400)
        return [
            {
                "time": recent,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
            }
        ]

    def get_balances_with_breakdown(self):
        return (
            {"BTC": 0.5, "ETH": 2.0, "USD": 1000.0},
            {"USDC": 500.0, "USD": 500.0},
        )


def test_product_to_symbol() -> None:
    assert product_to_symbol("BTC-USD") == "BTC"
    assert product_to_symbol("ETH-USD") == "ETH"


def test_normalize_pem_secret_unescapes_newlines() -> None:
    raw = "-----BEGIN EC PRIVATE KEY-----\\nabc\\n-----END EC PRIVATE KEY-----\\n"
    assert normalize_pem_secret(raw) == "-----BEGIN EC PRIVATE KEY-----\nabc\n-----END EC PRIVATE KEY-----\n"


def test_normalize_coinbase_balances() -> None:
    accounts = [
        {
            "currency": "BTC",
            "available_balance": {"value": "0.1"},
            "hold": {"value": "0.05"},
        },
        {
            "currency": "ETH",
            "available_balance": {"value": "1.0"},
            "hold": {"value": "0"},
        },
        {
            "currency": "USDC",
            "available_balance": {"value": "500"},
            "hold": {"value": "0"},
        },
    ]
    balances, cash_breakdown = normalize_coinbase_balances(accounts)
    assert balances["BTC"] == pytest.approx(0.15)
    assert balances["ETH"] == 1.0
    assert balances["USD"] == 500.0
    assert cash_breakdown["USDC"] == 500.0


def test_fetch_and_persist_coinbase_portfolio(config, conn) -> None:
    spot = config.exchanges.coinbase
    snap = fetch_portfolio_snapshot(FakeCoinbaseClient(), spot)
    assert snap.nav_usd > 0


def test_refresh_coinbase_missing_credentials(conn, tmp_path, monkeypatch) -> None:
    from alloccontext.config import load_config
    from alloccontext.store.db import connect

    cfg_path = tmp_path / "config.yaml"
    db = tmp_path / "test.db"
    cfg_path.write_text(
        f"""
paths:
  db: {db}
ingest:
  sources:
    coinbase: true
exchanges:
  coinbase:
    enabled: true
    pairs: [BTC-USD, ETH-USD]
"""
    )
    coinbase_config = load_config(cfg_path)
    connection = connect(coinbase_config.paths.db)
    monkeypatch.delenv("COINBASE_API_KEY", raising=False)
    monkeypatch.delenv("COINBASE_API_SECRET", raising=False)
    try:
        result = refresh_coinbase(connection, coinbase_config)
        assert result["ok"] is True
        assert result["skipped"] is True
        assert result["reason"] == "missing_coinbase_credentials"
    finally:
        connection.close()


def test_refresh_coinbase_success(conn, config, monkeypatch, tmp_path) -> None:
    from alloccontext.config import load_config
    from alloccontext.store.db import connect

    cfg_path = tmp_path / "config.yaml"
    db = tmp_path / "test.db"
    cfg_path.write_text(
        f"""
paths:
  db: {db}
ingest:
  sources:
    coinbase: true
exchanges:
  primary: coinbase
  coinbase:
    enabled: true
    pairs: [BTC-USD, ETH-USD]
"""
    )
    coinbase_config = load_config(cfg_path)
    connection = connect(coinbase_config.paths.db)
    monkeypatch.setenv("COINBASE_API_KEY", "organizations/test/apiKeys/test")
    monkeypatch.setenv(
        "COINBASE_API_SECRET",
        "-----BEGIN EC PRIVATE KEY-----\\ntest\\n-----END EC PRIVATE KEY-----\\n",
    )
    fake = FakeCoinbaseClient()
    try:
        with patch(
            "alloccontext.ingest.exchange.coinbase_adapter.build_coinbase_client",
            return_value=fake,
        ), patch(
            "alloccontext.ingest.exchange.coinbase_adapter.fetch_portfolio_snapshot",
            return_value=PortfolioSnapshot(
                ts="2026-05-21T12:00:00+00:00",
                nav_usd=1000.0,
                cash_usd=100.0,
                btc_usd=900.0,
                eth_usd=0.0,
                btc_pct=0.9,
                eth_pct=0.0,
                cash_pct=0.1,
                prices={"BTC": 90000.0},
            ),
        ):
            result = refresh_coinbase(connection, coinbase_config)
        assert result["ok"] is True
        assert result["rows"] >= 2
    finally:
        connection.close()
