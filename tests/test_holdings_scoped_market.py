from __future__ import annotations

import pytest

from alloccontext.ingest.alt_quote_store import upsert_alt_quote_snapshot
from alloccontext.ingest.alt_quotes import parse_cmc_alt_quotes, refresh_alt_quotes
from alloccontext.mcp.assets import resolve_view_assets
from alloccontext.mcp.handlers import get_market_context


def _seed_market_bars(conn) -> None:
    for pair, close in (("XBTUSD", 90000.0), ("ETHUSD", 3000.0)):
        conn.execute(
            """
            INSERT INTO market_bars(pair, interval_minutes, bar_ts, open, high, low, close)
            VALUES (?, 1440, 1716300000, ?, ?, ?, ?)
            """,
            (pair, close, close, close, close),
        )
    conn.commit()


def test_parse_cmc_alt_quotes_uses_payload_symbol() -> None:
    quotes = {
        "32196": {
            "symbol": "HYPE",
            "quote": {"USD": {"price": 25.0, "percent_change_24h": 1.2}},
        }
    }
    parsed = parse_cmc_alt_quotes(quotes)
    assert parsed["HYPE"]["price_usd"] == pytest.approx(25.0)
    assert parsed["HYPE"]["change_pct_24h"] == pytest.approx(1.2)


def test_resolve_view_assets_includes_cached_alt(conn) -> None:
    upsert_alt_quote_snapshot(
        conn,
        symbol="HYPE",
        snapshot_ts="2026-05-31T12:00:00+00:00",
        price_usd=25.0,
        change_pct_24h=1.2,
        source="coinmarketcap",
    )
    conn.commit()
    view_assets, omitted = resolve_view_assets(["BTC", "HYPE"], conn=conn)
    assert view_assets == ("BTC", "HYPE")
    assert omitted == ()


def test_get_market_context_includes_hype_when_cached(conn, config) -> None:
    _seed_market_bars(conn)
    upsert_alt_quote_snapshot(
        conn,
        symbol="HYPE",
        snapshot_ts="2026-05-31T12:00:00+00:00",
        price_usd=25.1,
        change_pct_24h=1.2,
        source="coingecko",
    )
    conn.commit()

    payload = get_market_context(
        conn,
        config,
        scope="daily",
        freshness="cached",
        assets=["BTC", "ETH", "HYPE"],
    )
    assert payload["assets"] == ["BTC", "ETH", "HYPE"]
    assert payload.get("assets_omitted") is None
    hype = payload["market"]["assets"]["hype"]
    assert hype["price_usd"] == pytest.approx(25.1)
    assert hype["change_pct"]["24h"] == pytest.approx(1.2)
    assert hype["source"] == "coingecko"


def test_get_market_context_lazy_refreshes_missing_hype(conn, config, monkeypatch) -> None:
    _seed_market_bars(conn)

    def fake_cmc(*, symbols, api_key, timeout):  # noqa: ARG001
        return {
            "32196": {
                "symbol": "HYPE",
                "quote": {"USD": {"price": 30.0, "percent_change_24h": 2.0}},
            }
        }

    monkeypatch.setattr(
        "alloccontext.ingest.coinmarketcap.fetch_cmc_quotes",
        fake_cmc,
    )
    monkeypatch.setenv("COINMARKETCAP_API_KEY", "test-key")

    payload = get_market_context(
        conn,
        config,
        scope="daily",
        freshness="cached",
        assets=["BTC", "ETH", "HYPE"],
    )
    assert "HYPE" not in (payload.get("assets_omitted") or [])
    assert payload["market"]["assets"]["hype"]["price_usd"] == pytest.approx(30.0)


def test_refresh_alt_quotes_persists_rows(conn, config, monkeypatch) -> None:
    def fake_cmc(*, symbols, api_key, timeout):  # noqa: ARG001
        return {
            "HYPE": {
                "symbol": "HYPE",
                "quote": {"USD": {"price": 22.0, "percent_change_24h": -0.5}},
            }
        }

    monkeypatch.setattr(
        "alloccontext.ingest.coinmarketcap.fetch_cmc_quotes",
        fake_cmc,
    )
    monkeypatch.setenv("COINMARKETCAP_API_KEY", "test-key")

    result = refresh_alt_quotes(conn, config, ["HYPE"])
    assert result["ok"] is True
    assert result["rows"] == 1

    payload = get_market_context(
        conn,
        config,
        freshness="cached",
        assets=["HYPE"],
    )
    assert payload["market"]["assets"]["hype"]["price_usd"] == pytest.approx(22.0)
