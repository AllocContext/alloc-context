from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from alloccontext.ingest.cf_history import load_cf_history
from alloccontext.ingest.kalshi import refresh_kalshi
from alloccontext.ingest.kalshi_api import fetch_series_market_quotes, refresh_kalshi_api
from alloccontext.ingest.kalshi_client import KalshiClient
from alloccontext.rollup.context import build_context_bundle


def _api_config(config):
    return replace(config, kalshi=replace(config.kalshi, use_api=True))


def test_fetch_series_market_quotes_fixture() -> None:
    payload = json.loads(Path("tests/fixtures/kalshi_markets_hourly.json").read_text())

    class FakeClient:
        def get_markets(self, **kwargs):
            assert kwargs.get("series_ticker") in {"KXBTCD", "KXETHD"}
            return payload

    quotes = fetch_series_market_quotes(FakeClient(), ["KXBTCD", "KXETHD"])
    assert len(quotes) == 2
    assert quotes[0].ticker.startswith("KXBTCD")


def test_refresh_kalshi_api_mock(conn, config, monkeypatch) -> None:
    cfg = _api_config(config)
    markets_payload = json.loads(
        Path("tests/fixtures/kalshi_markets_hourly.json").read_text()
    )

    def fake_get_markets(self, **kwargs):
        return markets_payload

    def fake_fetch_prices(indices, *, timeout=20.0):
        return {index: 1000.0 + idx for idx, index in enumerate(indices)}

    monkeypatch.setattr(KalshiClient, "get_markets", fake_get_markets)
    monkeypatch.setattr("alloccontext.ingest.kalshi_api.fetch_prices", fake_fetch_prices)

    result = refresh_kalshi_api(conn, cfg)
    assert result["ok"] is True
    assert result["rows"] == 1
    assert result["markets_sampled"] == 2
    assert result["tape_summary"]
    assert "hourly" in result["tape_summary"]

    history = load_cf_history(conn)
    assert "BRTI" in history
    assert len(history["BRTI"]) == 1


def test_refresh_kalshi_api_builds_context(conn, config, monkeypatch) -> None:
    cfg = _api_config(config)
    markets_payload = json.loads(
        Path("tests/fixtures/kalshi_markets_hourly.json").read_text()
    )

    monkeypatch.setattr(
        KalshiClient,
        "get_markets",
        lambda self, **kwargs: markets_payload,
    )
    monkeypatch.setattr(
        "alloccontext.ingest.kalshi_api.fetch_prices",
        lambda indices, *, timeout=20.0: dict.fromkeys(indices, 50000.0),
    )

    assert refresh_kalshi(conn, cfg)["ok"] is True
    bundle = build_context_bundle(
        conn,
        cfg,
        scope="daily",
        rollup=cfg.rollup,
        as_of=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
    )
    assert bundle["sentiment"]["kalshi"]["available"] is True
    assert bundle["sentiment"]["kalshi"]["tape_summary"]


def test_refresh_kalshi_file_fallback_when_api_disabled(conn, config, tmp_path: Path) -> None:
    tactical = tmp_path / "tactical_snapshot.json"
    tactical.write_text(Path("tests/fixtures/tactical_snapshot.json").read_text())
    cfg = replace(
        config,
        kalshi=replace(
            config.kalshi,
            use_api=False,
            fallback_tactical_snapshot=tactical,
        ),
    )
    result = refresh_kalshi(conn, cfg)
    assert result["ok"] is True
    assert result["source"] == "kalshi_files"
