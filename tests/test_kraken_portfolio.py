from __future__ import annotations

import time
from unittest.mock import patch

from alloccontext.ingest.kraken_client import normalize_kraken_balances, pair_to_symbol
from alloccontext.config import load_config
from alloccontext.ingest.kraken_portfolio import (
    PortfolioSnapshot,
    fetch_portfolio_snapshot,
    portfolio_from_balances,
    refresh_kraken,
    upsert_market_bars,
    upsert_portfolio_snapshot,
)
from alloccontext.store.db import connect


class FakeKrakenClient:
    def get_ticker(self, pair: str) -> dict[str, float]:
        return {"last": 100_000.0 if "XBT" in pair or pair == "XBTUSD" else 3_000.0}

    def get_ohlc(self, pair: str, interval: int = 1440) -> list[dict[str, float]]:
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
            {"ZUSD": 1000.0},
        )


def test_pair_to_symbol() -> None:
    assert pair_to_symbol("XBTUSD") == "BTC"
    assert pair_to_symbol("ETHUSD") == "ETH"


def test_normalize_kraken_balances() -> None:
    raw = {"XXBT": "0.1", "XETH": "1.0", "ZUSD": "500", "USDC": "100"}
    balances = normalize_kraken_balances(raw)
    assert balances["BTC"] == 0.1
    assert balances["ETH"] == 1.0
    assert balances["USD"] == 600.0


def test_portfolio_from_balances() -> None:
    snap = portfolio_from_balances(
        {"BTC": 1.0, "ETH": 0.0, "USD": 0.0},
        {"BTC": 100.0, "ETH": 0.0},
    )
    assert snap.nav_usd == 100.0
    assert snap.btc_pct == 1.0


def test_fetch_and_persist_portfolio(config, conn) -> None:
    snap = fetch_portfolio_snapshot(FakeKrakenClient(), config.exchanges.kraken)
    assert snap.nav_usd > 0
    upsert_portfolio_snapshot(conn, snap)
    row = conn.execute("SELECT nav_usd FROM portfolio_snapshots").fetchone()
    assert row["nav_usd"] == snap.nav_usd


def test_upsert_market_bars(conn) -> None:
    count = upsert_market_bars(
        conn,
        pair="XBTUSD",
        interval_minutes=1440,
        bars=[{"time": 1.0, "open": 1, "high": 2, "low": 0.5, "close": 1.5}],
    )
    assert count == 1


def test_refresh_kraken_missing_credentials_fails_when_primary(
    conn, config, monkeypatch
) -> None:
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    result = refresh_kraken(conn, config)
    assert result["ok"] is True
    assert result.get("skipped") is True
    assert result["reason"] == "missing_kraken_credentials"
    assert result["rows"] == 0
    assert result.get("market_bars", 0) == 0


def test_refresh_kraken_missing_credentials_still_fetches_ohlc_when_non_primary(
    tmp_path, monkeypatch
) -> None:
    """Non-primary Kraken keeps public OHLC ingest without portfolio creds."""
    cfg_path = tmp_path / "config.yaml"
    db = tmp_path / "test.db"
    cfg_path.write_text(
        f"""
paths:
  db: {db}
ingest:
  sources:
    kraken: true
exchanges:
  primary: coinbase
  kraken:
    enabled: true
    pairs: [XBTUSD, ETHUSD]
  coinbase:
    enabled: false
"""
    )
    dual_config = load_config(cfg_path)
    connection = connect(dual_config.paths.db)
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    fake = FakeKrakenClient()
    try:
        with patch(
            "alloccontext.ingest.exchange.kraken_adapter.build_kraken_client",
            return_value=fake,
        ):
            result = refresh_kraken(connection, dual_config)
        assert result["ok"] is True
        assert "skipped" not in result
        assert result["market_bars"] > 0
        assert result["rows"] == result["market_bars"]
        assert "portfolio" not in result
    finally:
        connection.close()


def test_refresh_kraken_success(conn, config, monkeypatch) -> None:
    monkeypatch.setenv("KRAKEN_API_KEY", "test-key")
    monkeypatch.setenv("KRAKEN_API_SECRET", "dGVzdA==")
    fake = FakeKrakenClient()
    with patch(
        "alloccontext.ingest.exchange.kraken_adapter.build_kraken_client",
        return_value=fake,
    ), patch(
        "alloccontext.ingest.exchange.kraken_adapter.fetch_portfolio_snapshot",
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
        result = refresh_kraken(conn, config)
    assert result["ok"] is True
    assert result["rows"] >= 2
