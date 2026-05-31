from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from alloccontext.ingest.alt_quote_store import register_quote_scope, upsert_alt_quote_snapshot
from alloccontext.ingest.alt_quotes import parse_cmc_alt_quotes, refresh_alt_quotes
from alloccontext.mcp.assets import resolve_view_assets
from alloccontext.mcp.handlers import get_market_context
from alloccontext.rollup.context import build_context_bundle


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


def test_resolve_view_assets_hype_only_when_cached(conn) -> None:
    upsert_alt_quote_snapshot(
        conn,
        symbol="HYPE",
        snapshot_ts="2026-05-31T12:00:00+00:00",
        price_usd=25.0,
        change_pct_24h=1.2,
        source="coinmarketcap",
    )
    conn.commit()
    view_assets, omitted = resolve_view_assets(["HYPE"], conn=conn)
    assert view_assets == ("HYPE",)
    assert omitted == ()


def test_register_quote_scope_persists_without_refresh(conn) -> None:
    register_quote_scope(conn, ["HYPE"])
    row = conn.execute(
        "SELECT symbol FROM alt_quote_scope WHERE symbol = ?",
        ("HYPE",),
    ).fetchone()
    assert row is not None
    assert row["symbol"] == "HYPE"


def test_build_context_bundle_saved_includes_portfolio_alt_market(conn, config) -> None:
    _seed_market_bars(conn)
    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "2026-05-31T12:00:00+00:00",
            1000.0,
            0.0,
            json.dumps(
                {
                    "holdings": [
                        {
                            "symbol": "HYPE",
                            "qty": 10.0,
                            "price_usd": 25.0,
                            "value_usd": 250.0,
                            "weight_pct": 1.0,
                            "kind": "alt",
                        }
                    ]
                }
            ),
            "{}",
        ),
    )
    upsert_alt_quote_snapshot(
        conn,
        symbol="HYPE",
        snapshot_ts="2026-05-31T12:00:00+00:00",
        price_usd=25.1,
        change_pct_24h=1.2,
        source="coingecko",
    )
    conn.commit()

    bundle = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        as_of=datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc),
        save_snapshot=True,
    )
    assert bundle["market"]["assets"]["hype"]["price_usd"] == pytest.approx(25.1)

    row = conn.execute(
        "SELECT context_json FROM context_snapshots WHERE scope = ?",
        ("daily",),
    ).fetchone()
    saved = json.loads(row["context_json"])
    assert saved["market"]["assets"]["hype"]["price_usd"] == pytest.approx(25.1)


def test_get_market_context_live_fails_without_quote_keys(
    conn, config, monkeypatch, mock_live_ingest_ok
) -> None:
    _seed_market_bars(conn)
    monkeypatch.delenv("COINMARKETCAP_API_KEY", raising=False)
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    payload = get_market_context(
        conn,
        config,
        freshness="live",
        assets=["HYPE"],
    )
    assert payload["available"] is False
    assert payload["reason"] == "live_alt_quote_refresh_failed"
    assert payload["ingest"]["alt_quotes"]["reason"] == "no_quote_api_keys"
