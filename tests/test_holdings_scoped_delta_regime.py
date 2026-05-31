from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from alloccontext.ingest.alt_quote_store import upsert_alt_quote_snapshot
from alloccontext.mcp.handlers import get_context_bundle
from alloccontext.rollup.context import build_context_bundle
from alloccontext.rollup.delta import build_delta_context
from alloccontext.rollup.regime import build_regime_context


def _market_with_hype(*, price: float, change_24h: float | None = None) -> dict:
    block: dict = {
        "pair": "HYPE-USD",
        "price_usd": price,
        "source": "coingecko",
    }
    if change_24h is not None:
        block["change_pct"] = {"24h": change_24h}
    return {
        "available": True,
        "assets": {
            "btc": {"pair": "BTC-USD", "price_usd": 70_000.0, "change_pct": {"1_bar": 0.5}},
            "hype": block,
        },
    }


def test_build_delta_context_includes_alt_price_shift() -> None:
    now = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)
    market = _market_with_hype(price=30.0)
    prior = {
        "market": _market_with_hype(price=25.0),
    }
    delta = build_delta_context(
        None,  # type: ignore[arg-type]
        now=now,
        portfolio={"available": False},
        sentiment={"available": False},
        market=market,
        prior_context=prior,
    )
    assert delta["market"]["hype_change_pct_since_prior"] == pytest.approx(20.0)
    assert any("HYPE +20.00% since prior snapshot" in line for line in delta["notable_shifts"])


def test_build_delta_context_skips_alt_without_prior_mark() -> None:
    now = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)
    market = _market_with_hype(price=30.0)
    prior = {"market": {"available": True, "assets": {"btc": {"price_usd": 70_000.0}}}}
    delta = build_delta_context(
        None,  # type: ignore[arg-type]
        now=now,
        portfolio={"available": False},
        sentiment={"available": False},
        market=market,
        prior_context=prior,
    )
    assert "hype_change_pct_since_prior" not in (delta.get("market") or {})


def test_build_regime_context_alt_holding_move_hint() -> None:
    regime = build_regime_context(
        portfolio={
            "available": True,
            "holdings": [
                {
                    "symbol": "HYPE",
                    "weight_pct": 0.15,
                    "value_usd": 1500.0,
                }
            ],
        },
        sentiment={"available": False},
        delta={"available": False},
        market=_market_with_hype(price=30.0, change_24h=6.5),
        prior_as_of="2026-05-30T12:00:00+00:00",
    )
    holding_hints = [hint for hint in regime["hints"] if hint["kind"] == "holding_move"]
    assert len(holding_hints) == 1
    assert "HYPE" in holding_hints[0]["text"]
    assert "15.0% weight" in holding_hints[0]["text"]


def test_build_regime_context_uses_delta_move_for_alt_hint() -> None:
    regime = build_regime_context(
        portfolio={
            "available": True,
            "holdings": [{"symbol": "HYPE", "weight_pct": 0.20}],
        },
        sentiment={"available": False},
        delta={
            "available": True,
            "market": {"hype_change_pct_since_prior": -6.0},
            "notable_shifts": ["HYPE -6.00% since prior snapshot"],
        },
        market=_market_with_hype(price=30.0),
        prior_as_of="2026-05-30T12:00:00+00:00",
    )
    assert any(hint["kind"] == "holding_move" for hint in regime["hints"])


def _seed_market_bars(conn) -> None:
    for pair, close in (("XBTUSD", 90_000.0), ("ETHUSD", 3_000.0)):
        conn.execute(
            """
            INSERT INTO market_bars(pair, interval_minutes, bar_ts, open, high, low, close)
            VALUES (?, 1440, 1716300000, ?, ?, ?, ?)
            """,
            (pair, close, close, close, close),
        )
    conn.commit()


def test_get_context_bundle_delta_regime_reference_hype(conn, config) -> None:
    _seed_market_bars(conn)
    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "2026-05-31T12:00:00+00:00",
            10_000.0,
            0.0,
            json.dumps(
                {
                    "holdings": [
                        {
                            "symbol": "BTC",
                            "weight_pct": 0.70,
                            "value_usd": 7000.0,
                        },
                        {
                            "symbol": "HYPE",
                            "weight_pct": 0.15,
                            "value_usd": 1500.0,
                        },
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
        price_usd=30.0,
        change_pct_24h=6.0,
        source="coingecko",
    )
    conn.commit()

    prior_bundle = {
        "scope": "daily",
        "as_of": "2026-05-30T12:00:00+00:00",
        "portfolio": {
            "available": True,
            "nav_usd": 9_800.0,
            "holdings": [
                {"symbol": "HYPE", "weight_pct": 0.14},
            ],
        },
        "market": _market_with_hype(price=25.0),
        "sentiment": {"available": False},
        "delta": {"available": False},
    }
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        VALUES (?, ?, ?)
        """,
        ("daily", prior_bundle["as_of"], json.dumps(prior_bundle)),
    )
    conn.commit()

    bundle = get_context_bundle(
        conn,
        config,
        scope="daily",
        freshness="cached",
        assets=["BTC", "HYPE"],
    )
    shifts = bundle["delta"].get("notable_shifts") or []
    assert any("HYPE" in line for line in shifts)
    assert any(
        hint.get("kind") == "holding_move" and "HYPE" in hint.get("text", "")
        for hint in bundle["regime"].get("hints") or []
    )


def test_get_context_bundle_live_alt_refresh_wired(config, conn, monkeypatch) -> None:
    _seed_market_bars(conn)

    def fake_refresh(_conn, _cfg, symbols):
        assert "HYPE" in symbols
        return {"ok": True, "rows": 1, "symbols_fetched": ["HYPE"]}

    monkeypatch.setattr(
        "alloccontext.ingest.alt_quotes.refresh_alt_quotes",
        fake_refresh,
    )
    monkeypatch.setenv("COINMARKETCAP_API_KEY", "test-key")

    payload = get_context_bundle(
        conn,
        config,
        freshness="live",
        assets=["BTC", "ETH", "HYPE"],
    )
    assert payload.get("reason") != "live_alt_quote_refresh_failed"
    assert payload["ingest"]["alt_quotes"]["ok"] is True
