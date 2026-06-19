from __future__ import annotations

from datetime import date, timedelta

import pytest

from alloccontext.ingest.onchain_cycle import (
    BRK_DAY1_ORIGIN,
    day1_index_to_date,
    parse_bitview_bulk,
    refresh_onchain_cycle,
    upsert_onchain_cycle_rows,
)
from alloccontext.rollup.cycle import build_cycle_context
from alloccontext.rollup.regime import build_regime_context
from alloccontext.timeutil import utc_now_iso


def test_day1_index_to_date_matches_brk_origin() -> None:
    assert day1_index_to_date(0) == BRK_DAY1_ORIGIN
    assert day1_index_to_date(6379) == date(2026, 6, 20)


def test_parse_bitview_bulk_maps_series_to_rows() -> None:
    payload = [
        {"start": 6377, "end": 6378, "data": [55.0, 54.0]},
        {"start": 6377, "end": 6378, "data": [45.0, 46.0]},
        {"start": 6377, "end": 6378, "data": [100.0, 99.0]},
        {"start": 6377, "end": 6378, "data": [90.0, 91.0]},
    ]
    rows = parse_bitview_bulk(payload)
    assert len(rows) == 2
    assert rows[0]["as_of_date"] == day1_index_to_date(6377).isoformat()
    assert rows[0]["supply_profit_pct"] == 55.0
    assert rows[0]["supply_loss_pct"] == 45.0
    assert rows[1]["supply_profit_pct"] == 54.0


def test_upsert_onchain_cycle_rows(conn) -> None:
    rows = [
        {
            "as_of_date": "2026-06-01",
            "supply_profit_pct": 60.0,
            "supply_loss_pct": 40.0,
            "supply_profit_btc": 1.0,
            "supply_loss_btc": 2.0,
            "btc_price_usd": None,
        }
    ]
    count = upsert_onchain_cycle_rows(conn, rows, source="bitview")
    conn.commit()
    assert count == 1
    row = conn.execute(
        "SELECT source FROM onchain_cycle_daily WHERE as_of_date = ?",
        ("2026-06-01",),
    ).fetchone()
    assert row["source"] == "bitview"


def test_refresh_onchain_cycle_uses_health_and_bulk(conn, config, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_health(*, base_url: str, timeout: float) -> dict[str, object]:
        captured["health_url"] = base_url
        return {"ok": True}

    def fake_bulk(*, base_url: str, start: int, timeout: float) -> list[dict]:
        captured["start"] = start
        return [
            {"start": 6378, "end": 6378, "data": [52.0]},
            {"start": 6378, "end": 6378, "data": [48.0]},
            {"start": 6378, "end": 6378, "data": [100.0]},
            {"start": 6378, "end": 6378, "data": [90.0]},
        ]

    monkeypatch.setattr(
        "alloccontext.ingest.onchain_cycle.check_provider_health",
        fake_health,
    )
    monkeypatch.setattr(
        "alloccontext.ingest.onchain_cycle.fetch_bitview_bulk",
        fake_bulk,
    )

    result = refresh_onchain_cycle(conn, config)
    assert result["ok"] is True
    assert result["rows"] == 1
    assert captured["start"] == -config.onchain.cycle.backfill_days


def test_build_cycle_context_capitulation(conn, config) -> None:
    today = date.today()
    week_ago = (today - timedelta(days=8)).isoformat()
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (week_ago, 52.0, 48.0, None, None, None, "bitview", utc_now_iso()),
    )
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            today.isoformat(),
            48.0,
            52.0,
            None,
            None,
            None,
            "bitview",
            utc_now_iso(),
        ),
    )
    conn.commit()

    cycle = build_cycle_context(conn, config)
    assert cycle["available"] is True
    assert cycle["phase"] == "CAPITULATION"
    assert cycle["convergence"] is True
    assert cycle["history_7d"]["available"] is True
    assert "supply_profit_pct_delta" in cycle["history_7d"]


def test_build_cycle_context_distribution(conn, config) -> None:
    today = date.today()
    week_ago = (today - timedelta(days=8)).isoformat()
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (week_ago, 86.0, 14.0, None, None, None, "bitview", utc_now_iso()),
    )
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            today.isoformat(),
            82.0,
            18.0,
            None,
            None,
            None,
            "bitview",
            utc_now_iso(),
        ),
    )
    conn.commit()

    cycle = build_cycle_context(conn, config)
    assert cycle["phase"] == "DISTRIBUTION"


def test_build_cycle_context_stale_data(conn, config) -> None:
    stale = (date.today() - timedelta(days=10)).isoformat()
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (stale, 60.0, 40.0, None, None, None, "bitview", utc_now_iso()),
    )
    conn.commit()
    cycle = build_cycle_context(conn, config)
    assert cycle["available"] is False
    assert cycle["reason"] == "stale_data"


def test_regime_cycle_does_not_change_risk_off(conn, config) -> None:
    today = date.today().isoformat()
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (today, 48.0, 52.0, None, None, None, "bitview", utc_now_iso()),
    )
    conn.commit()

    regime = build_regime_context(
        portfolio={"available": False},
        sentiment={
            "available": True,
            "fear_greed": {"value": 50, "classification": "Neutral"},
        },
        delta={"available": False},
        prior_as_of=None,
        conn=conn,
        config=config,
    )
    assert regime["cycle"]["available"] is True
    assert regime["cycle"]["phase"] == "CAPITULATION"
    assert regime["risk_off"]["score"] == 0


def test_refresh_onchain_cycle_glassnode_skips_without_key(conn, config, monkeypatch) -> None:
    from dataclasses import replace

    from alloccontext.config import OnchainConfig, OnchainCycleConfig

    cfg = replace(
        config,
        onchain=OnchainConfig(
            cycle=replace(
                config.onchain.cycle,
                provider="glassnode",
            )
        ),
    )
    monkeypatch.delenv("GLASSNODE_API_KEY", raising=False)
    result = refresh_onchain_cycle(conn, cfg)
    assert result["skipped"] is True
    assert result["reason"] == "missing_glassnode_key"


def test_refresh_onchain_cycle_unhealthy_provider(conn, config, monkeypatch) -> None:
    monkeypatch.setattr(
        "alloccontext.ingest.onchain_cycle.check_provider_health",
        lambda **kwargs: {"ok": False, "error": "provider_unavailable"},
    )
    result = refresh_onchain_cycle(conn, config)
    assert result["ok"] is False
    assert result["error"] == "provider_unavailable"


def test_build_cycle_context_euphoria(conn, config) -> None:
    today = date.today().isoformat()
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (today, 92.0, 8.0, None, None, None, "bitview", utc_now_iso()),
    )
    conn.commit()
    cycle = build_cycle_context(conn, config)
    assert cycle["phase"] == "EUPHORIA"


def test_build_cycle_context_recovery(conn, config) -> None:
    today = date.today()
    week_ago = (today - timedelta(days=8)).isoformat()
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (week_ago, 55.0, 45.0, None, None, None, "bitview", utc_now_iso()),
    )
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            today.isoformat(),
            58.0,
            42.0,
            None,
            None,
            None,
            "bitview",
            utc_now_iso(),
        ),
    )
    conn.commit()
    cycle = build_cycle_context(conn, config)
    assert cycle["phase"] == "RECOVERY"


def test_d9_convergence_fixture_spread_within_tolerance() -> None:
    """Nov 2022-style convergence: profit/loss within 5pp (ADR-021 D9 sketch)."""
    profit = 49.5
    loss = 50.5
    spread = abs(profit - loss)
    assert spread <= 5.0


def test_fetch_bitview_bulk_http_error(monkeypatch) -> None:
    import urllib.error

    from alloccontext.ingest.onchain_cycle import fetch_bitview_bulk

    def fake_urlopen(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://bitview.space/api/series/bulk",
            503,
            "Service Unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(ValueError, match="bitview bulk series"):
        fetch_bitview_bulk(base_url="https://bitview.space", start=-1, timeout=5.0)


def test_refresh_onchain_cycle_incremental_start(conn, config, monkeypatch) -> None:
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-06-01", 60.0, 40.0, 1.0, 2.0, None, "bitview", utc_now_iso()),
    )
    conn.commit()
    captured: dict[str, int] = {}

    monkeypatch.setattr(
        "alloccontext.ingest.onchain_cycle.check_provider_health",
        lambda **kwargs: {"ok": True},
    )

    def fake_bulk(*, base_url: str, start: int, timeout: float) -> list[dict]:
        captured["start"] = start
        return [
            {"start": 6378, "end": 6378, "data": [52.0]},
            {"start": 6378, "end": 6378, "data": [48.0]},
            {"start": 6378, "end": 6378, "data": [100.0]},
            {"start": 6378, "end": 6378, "data": [90.0]},
        ]

    monkeypatch.setattr(
        "alloccontext.ingest.onchain_cycle.fetch_bitview_bulk",
        fake_bulk,
    )
    result = refresh_onchain_cycle(conn, config)
    assert result["ok"] is True
    assert captured["start"] == -14


def test_build_cycle_context_includes_btc_amounts(conn, config) -> None:
    today = date.today().isoformat()
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (today, 60.0, 40.0, 12.5, 8.25, None, "bitview", utc_now_iso()),
    )
    conn.commit()
    cycle = build_cycle_context(conn, config)
    assert cycle["supply_profit_btc"] == 12.5
    assert cycle["supply_loss_btc"] == 8.25


def test_build_cycle_context_neutral_near_convergence(conn, config) -> None:
    today = date.today().isoformat()
    conn.execute(
        """
        INSERT INTO onchain_cycle_daily(
          as_of_date, supply_profit_pct, supply_loss_pct,
          supply_profit_btc, supply_loss_btc, btc_price_usd, source, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (today, 35.0, 34.9, None, None, None, "bitview", utc_now_iso()),
    )
    conn.commit()
    cycle = build_cycle_context(conn, config)
    assert cycle["phase"] == "NEUTRAL"
    assert cycle["phase_reason"] == "convergence_below_capitulation_loss_floor"


def test_parse_bitview_bulk_length_mismatch() -> None:
    payload = [
        {"start": 1, "end": 2, "data": [1.0, 2.0]},
        {"start": 1, "end": 2, "data": [3.0]},
        {"start": 1, "end": 2, "data": [4.0, 5.0]},
        {"start": 1, "end": 2, "data": [6.0, 7.0]},
    ]
    with pytest.raises(ValueError, match="length mismatch"):
        parse_bitview_bulk(payload)


def test_refresh_onchain_cycle_brk_requires_base_url(conn, config) -> None:
    from dataclasses import replace

    from alloccontext.config import OnchainConfig

    cfg = replace(
        config,
        onchain=OnchainConfig(
            cycle=replace(
                config.onchain.cycle,
                provider="brk",
                brk_base_url=None,
            )
        ),
    )
    result = refresh_onchain_cycle(conn, cfg)
    assert result["ok"] is False
    assert "brk_base_url" in result["error"]


def test_check_provider_health_unhealthy(monkeypatch) -> None:
    import json

    from alloccontext.ingest.onchain_cycle import check_provider_health

    class FakeResponse:
        def read(self):
            return json.dumps({"status": "degraded"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse())
    result = check_provider_health(base_url="https://bitview.space", timeout=5.0)
    assert result["ok"] is False


def test_refresh_onchain_cycle_glassnode_upserts(conn, config, monkeypatch) -> None:
    from dataclasses import replace

    from alloccontext.config import OnchainConfig

    cfg = replace(
        config,
        onchain=OnchainConfig(
            cycle=replace(
                config.onchain.cycle,
                provider="glassnode",
            )
        ),
    )
    monkeypatch.setenv("GLASSNODE_API_KEY", "test-key")
    monkeypatch.setattr(
        "alloccontext.ingest.onchain_cycle.fetch_glassnode_supply_pl",
        lambda **kwargs: [
            {
                "as_of_date": date.today().isoformat(),
                "supply_profit_pct": 61.0,
                "supply_loss_pct": 39.0,
                "supply_profit_btc": None,
                "supply_loss_btc": None,
                "btc_price_usd": None,
            }
        ],
    )
    result = refresh_onchain_cycle(conn, cfg)
    assert result["ok"] is True
    assert result["rows"] == 1
