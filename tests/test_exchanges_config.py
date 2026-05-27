from __future__ import annotations

from alloccontext.config import load_config


def test_exchanges_from_example_config(config) -> None:
    assert config.exchanges.primary == "kraken"
    assert config.exchanges.kraken.enabled is True
    assert config.exchanges.kraken.pairs == ["XBTUSD", "ETHUSD"]
    assert config.kraken.pairs == config.exchanges.kraken.pairs


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
