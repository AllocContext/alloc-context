from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from alloccontext.ingest.alt_quote_store import upsert_alt_quote_snapshot
from alloccontext.mcp.assets import filter_delta_market
from alloccontext.mcp.handlers import get_context_at, get_context_bundle
from alloccontext.rollup.comparison import compare_context_bundles
from alloccontext.rollup.delta import build_delta_context
from alloccontext.rollup.material_moves import build_portfolio_material_moves
from alloccontext.rollup.regime import build_regime_context


def _portfolio_with_hype(*, weight: float = 0.15) -> dict:
    return {
        "available": True,
        "holdings": [
            {
                "symbol": "HYPE",
                "weight_pct": weight,
                "value_usd": 1500.0,
            }
        ],
    }


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


def _market_with_sol_and_hype(*, hype_price: float, sol_price: float) -> dict:
    return {
        "available": True,
        "assets": {
            "hype": {"pair": "HYPE-USD", "price_usd": hype_price, "source": "coingecko"},
            "sol": {"pair": "SOL-USD", "price_usd": sol_price, "source": "coingecko"},
        },
    }


def test_build_delta_context_includes_alt_price_shift_for_held_symbol() -> None:
    now = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)
    market = _market_with_hype(price=30.0)
    prior = {"market": _market_with_hype(price=25.0)}
    delta = build_delta_context(
        None,  # type: ignore[arg-type]
        now=now,
        portfolio=_portfolio_with_hype(),
        sentiment={"available": False},
        market=market,
        prior_context=prior,
    )
    assert delta["market"]["hype_change_pct_since_prior"] == pytest.approx(20.0)
    assert any("HYPE +20.00% since prior snapshot" in line for line in delta["notable_shifts"])


def test_build_delta_context_skips_unheld_market_alts() -> None:
    now = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)
    market = _market_with_sol_and_hype(hype_price=30.0, sol_price=100.0)
    prior = {
        "market": _market_with_sol_and_hype(hype_price=25.0, sol_price=90.0),
    }
    delta = build_delta_context(
        None,  # type: ignore[arg-type]
        now=now,
        portfolio=_portfolio_with_hype(),
        sentiment={"available": False},
        market=market,
        prior_context=prior,
    )
    assert "hype_change_pct_since_prior" in delta["market"]
    assert "sol_change_pct_since_prior" not in delta["market"]


def test_build_delta_context_skips_alt_without_prior_mark() -> None:
    now = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)
    market = _market_with_hype(price=30.0)
    prior = {"market": {"available": True, "assets": {"btc": {"price_usd": 70_000.0}}}}
    delta = build_delta_context(
        None,  # type: ignore[arg-type]
        now=now,
        portfolio=_portfolio_with_hype(),
        sentiment={"available": False},
        market=market,
        prior_context=prior,
    )
    assert "hype_change_pct_since_prior" not in (delta.get("market") or {})


def test_build_delta_context_btc_current_price_from_market_block() -> None:
    now = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)
    market = {
        "available": True,
        "assets": {
            "btc": {"price_usd": 72_000.0},
        },
    }
    prior = {"market": {"available": True, "assets": {"btc": {"price_usd": 70_000.0}}}}
    delta = build_delta_context(
        None,  # type: ignore[arg-type]
        now=now,
        portfolio={"available": False},
        sentiment={"available": False},
        market=market,
        prior_context=prior,
    )
    assert delta["market"]["btc_change_pct_since_prior"] == pytest.approx(2.86)


def test_build_portfolio_material_moves() -> None:
    moves = build_portfolio_material_moves(
        portfolio=_portfolio_with_hype(),
        market=_market_with_hype(price=30.0, change_24h=6.5),
        delta={"available": False},
    )
    assert len(moves) == 1
    assert moves[0]["symbol"] == "HYPE"
    assert "15.0% weight" in moves[0]["text"]


def test_build_portfolio_material_moves_uses_delta_market() -> None:
    moves = build_portfolio_material_moves(
        portfolio={"available": True, "holdings": [{"symbol": "HYPE", "weight_pct": 0.20}]},
        market=_market_with_hype(price=30.0),
        delta={
            "available": True,
            "market": {"hype_change_pct_since_prior": -6.0},
        },
    )
    assert len(moves) == 1
    assert moves[0]["move_pct"] == pytest.approx(-6.0)


def test_build_regime_context_excludes_sleeve_shifts_from_hints() -> None:
    regime = build_regime_context(
        portfolio={"available": True, "holdings": [{"symbol": "HYPE", "weight_pct": 0.20}]},
        sentiment={"available": False},
        delta={
            "available": True,
            "notable_shifts": [
                "HYPE -6.00% since prior snapshot",
                "BTC allocation +2.0 pp",
                "Portfolio Δ $+500.00 since prior snapshot",
            ],
        },
        market=_market_with_hype(price=30.0),
        prior_as_of="2026-05-30T12:00:00+00:00",
    )
    assert regime["comparison"]["market_shifts"] == ["HYPE -6.00% since prior snapshot"]
    assert "BTC allocation +2.0 pp" in regime["comparison"]["sleeve_shifts"]
    assert not any(hint["kind"] == "holding_move" for hint in regime["hints"])
    assert len([hint for hint in regime["hints"] if hint["kind"] == "delta"]) == 1


def test_filter_delta_market_keeps_hype_shift() -> None:
    delta = {
        "available": True,
        "notable_shifts": [
            "BTC +2.10% since prior snapshot",
            "HYPE +20.00% since prior snapshot",
        ],
        "market": {
            "btc_change_pct_since_prior": 2.1,
            "hype_change_pct_since_prior": 20.0,
        },
    }
    filtered = filter_delta_market(delta, ("HYPE",))
    assert filtered["notable_shifts"] == ["HYPE +20.00% since prior snapshot"]
    assert filtered["market"] == {"hype_change_pct_since_prior": 20.0}


def test_compare_context_bundles_includes_saved_alt_shifts() -> None:
    prior = {
        "as_of": "2026-05-30T12:00:00+00:00",
        "delta": {"available": True, "notable_shifts": []},
    }
    current = {
        "as_of": "2026-05-31T12:00:00+00:00",
        "delta": {
            "available": True,
            "notable_shifts": ["HYPE +20.00% since prior snapshot"],
        },
    }
    diff = compare_context_bundles(prior, current)
    assert "HYPE +20.00% since prior snapshot" in diff["notable_shifts"]


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
                        {"symbol": "BTC", "weight_pct": 0.70, "value_usd": 7000.0},
                        {"symbol": "HYPE", "weight_pct": 0.15, "value_usd": 1500.0},
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
            "holdings": [{"symbol": "HYPE", "weight_pct": 0.14}],
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
    assert not any("SOL" in line for line in shifts)
    material = bundle["portfolio"].get("material_moves") or []
    assert any(row.get("symbol") == "HYPE" for row in material)
    assert not any(
        hint.get("kind") == "holding_move" for hint in bundle["regime"].get("hints") or []
    )


def test_get_context_at_rebuilds_regime_for_filtered_hype(conn, config) -> None:
    upsert_alt_quote_snapshot(
        conn,
        symbol="HYPE",
        snapshot_ts="2026-05-31T12:00:00+00:00",
        price_usd=30.0,
        change_pct_24h=6.5,
        source="coingecko",
    )
    snapshot = {
        "scope": "daily",
        "as_of": "2026-05-31T12:00:00+00:00",
        "portfolio": {
            "available": True,
            "holdings": [{"symbol": "HYPE", "weight_pct": 0.15}],
        },
        "market": _market_with_hype(price=30.0, change_24h=6.5),
        "sentiment": {"available": False},
        "delta": {
            "available": True,
            "notable_shifts": ["HYPE +20.00% since prior snapshot"],
            "market": {"hype_change_pct_since_prior": 20.0},
        },
        "regime": {"available": True, "hints": []},
    }
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        VALUES (?, ?, ?)
        """,
        ("daily", snapshot["as_of"], json.dumps(snapshot)),
    )
    conn.commit()

    payload = get_context_at(
        conn,
        config,
        scope="daily",
        as_of=snapshot["as_of"],
        match="exact",
        assets=["HYPE"],
    )
    assert payload["assets"] == ["HYPE"]
    assert not any(
        hint.get("kind") == "holding_move" for hint in payload["regime"].get("hints") or []
    )


def test_get_context_bundle_live_alt_refresh_wired(
    config, conn, monkeypatch, mock_live_ingest_ok
) -> None:
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
