from __future__ import annotations

from unittest.mock import patch

from alloccontext.config import load_config


def test_exchanges_from_example_config(config) -> None:
    assert config.exchanges.primary == "kraken"
    assert config.exchanges.kraken.enabled is True
    assert config.exchanges.kraken.pairs == ["XBTUSD", "ETHUSD"]
    assert config.exchanges.coinbase.enabled is False
    assert config.exchanges.coinbase.pairs == ["BTC-USD", "ETH-USD"]
    assert config.kraken.pairs == config.exchanges.kraken.pairs


def test_coinbase_primary_spot(tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
ingest:
  sources:
    coinbase: true
exchanges:
  primary: coinbase
  coinbase:
    enabled: true
    pairs: [BTC-USD]
"""
    )
    config = load_config(cfg_path)
    spot = config.exchanges.primary_spot()
    assert spot.pairs == ["BTC-USD"]


def test_legacy_kraken_block_without_exchanges(tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
ingest:
  sources:
    kraken: true
kraken:
  pairs: [XBTUSD]
  ohlc_interval_minutes: 60
"""
    )
    config = load_config(cfg_path)
    assert config.exchanges.primary == "kraken"
    assert config.exchanges.kraken.pairs == ["XBTUSD"]
    assert config.exchanges.kraken.ohlc_interval_minutes == 60


def test_exchanges_enabled_flag(tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
ingest:
  sources:
    kraken: true
exchanges:
  primary: kraken
  kraken:
    enabled: false
    pairs: [XBTUSD, ETHUSD]
"""
    )
    config = load_config(cfg_path)
    assert config.exchanges.kraken.enabled is False


def test_refresh_skips_disabled_exchange(conn, tmp_path) -> None:
    from alloccontext.store.db import connect

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
  primary: kraken
  kraken:
    enabled: false
    pairs: [XBTUSD, ETHUSD]
"""
    )
    config = load_config(cfg_path)
    connection = connect(config.paths.db)
    try:
        from alloccontext.ingest.exchange.registry import refresh_exchange

        result = refresh_exchange(connection, config, "kraken")
        assert result["skipped"] is True
        assert result["reason"] == "exchange_disabled"
    finally:
        connection.close()


def test_coinbase_ingest_does_not_overwrite_kraken_portfolio(
    conn, config, monkeypatch, tmp_path
) -> None:
    from alloccontext.ingest.kraken_portfolio import PortfolioSnapshot, upsert_portfolio_snapshot
    from alloccontext.ingest.exchange.registry import refresh_exchange
    from alloccontext.store.db import connect

    cfg_path = tmp_path / "config.yaml"
    db = tmp_path / "test.db"
    cfg_path.write_text(
        f"""
paths:
  db: {db}
ingest:
  sources:
    kraken: true
    coinbase: true
exchanges:
  primary: kraken
  kraken:
    enabled: true
    pairs: [XBTUSD, ETHUSD]
  coinbase:
    enabled: true
    pairs: [BTC-USD, ETH-USD]
"""
    )
    dual_config = load_config(cfg_path)
    connection = connect(dual_config.paths.db)
    kraken_snap = PortfolioSnapshot(
        ts="2026-05-27T12:00:00+00:00",
        nav_usd=630.0,
        cash_usd=177.0,
        btc_usd=315.0,
        eth_usd=138.0,
        btc_pct=0.5,
        eth_pct=0.22,
        cash_pct=0.28,
        prices={"BTC": 75000.0, "ETH": 2000.0},
    )
    upsert_portfolio_snapshot(connection, kraken_snap)
    monkeypatch.setenv("COINBASE_API_KEY", "organizations/test/apiKeys/test")
    monkeypatch.setenv(
        "COINBASE_API_SECRET",
        "-----BEGIN EC PRIVATE KEY-----\\ntest\\n-----END EC PRIVATE KEY-----\\n",
    )
    empty_coinbase = PortfolioSnapshot(
        ts="2026-05-27T12:00:01+00:00",
        nav_usd=0.0,
        cash_usd=0.0,
        btc_usd=0.0,
        eth_usd=0.0,
        btc_pct=0.0,
        eth_pct=0.0,
        cash_pct=0.0,
        prices={"BTC": 75000.0, "ETH": 2000.0},
    )
    try:
        with patch(
            "alloccontext.ingest.exchange.coinbase_adapter.build_coinbase_client"
        ) as mock_client, patch(
            "alloccontext.ingest.exchange.coinbase_adapter.fetch_portfolio_snapshot",
            return_value=empty_coinbase,
        ):
            mock_client.return_value.get_ohlc.return_value = []
            result = refresh_exchange(connection, dual_config, "coinbase")
        assert result["ok"] is True
        assert "portfolio" not in result
        row = connection.execute(
            "SELECT nav_usd, allocation_json FROM portfolio_snapshots ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        assert row["nav_usd"] == 630.0
    finally:
        connection.close()
