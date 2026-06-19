from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

from alloccontext.mcp.handlers import get_context_bundle
from alloccontext.rollup.context import build_context_bundle


def _seed_portfolio(conn, *, ts: str, nav: float) -> None:
    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ts, nav, 0.0, json.dumps({"BTC": 0.7, "ETH": 0.3, "CASH": 0.0}), "{}"),
    )
    conn.commit()


def test_build_context_bundle_read_does_not_save_snapshot(conn, config) -> None:
    _seed_portfolio(conn, ts="2026-05-21T12:00:00+00:00", nav=1000.0)
    build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        as_of=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
    )
    count = conn.execute("SELECT COUNT(*) FROM context_snapshots").fetchone()[0]
    assert count == 0


def test_build_context_bundle_save_snapshot_persists(conn, config) -> None:
    _seed_portfolio(conn, ts="2026-05-21T12:00:00+00:00", nav=1000.0)
    build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        as_of=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
        save_snapshot=True,
    )
    count = conn.execute("SELECT COUNT(*) FROM context_snapshots").fetchone()[0]
    assert count == 1


def test_mcp_get_context_bundle_does_not_pollute_snapshots(conn, config) -> None:
    _seed_portfolio(conn, ts="2026-05-21T12:00:00+00:00", nav=1000.0)
    build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        as_of=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
        save_snapshot=True,
    )
    get_context_bundle(conn, config, scope="daily", freshness="cached")
    get_context_bundle(conn, config, scope="daily", freshness="cached")
    rows = conn.execute(
        "SELECT as_of FROM context_snapshots WHERE scope = 'daily'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["as_of"] == "2026-05-20T12:00:00+00:00"


def test_get_context_bundle_live_fails_closed_on_alt_refresh(
    config, conn, mock_live_ingest_ok
) -> None:
    """Live bundle calls fail closed when requested alt quote refresh fails."""
    import json

    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "2026-05-21T12:00:00+00:00",
            1000.0,
            0.0,
            json.dumps({"BTC": 0.7, "ETH": 0.3, "CASH": 0.0}),
            "{}",
        ),
    )
    conn.commit()
    with patch(
        "alloccontext.ingest.alt_quotes.refresh_alt_quotes",
        return_value={
            "ok": False,
            "rows": 0,
            "symbols_requested": ["HYPE"],
            "symbols_fetched": [],
            "symbols_missing": ["HYPE"],
        },
    ):
        payload = get_context_bundle(
            conn,
            config,
            scope="daily",
            freshness="live",
            assets=["HYPE"],
        )

    assert payload["available"] is False
    assert payload["reason"] == "live_alt_quote_refresh_failed"
    assert payload["freshness"] == "live"
    assert "bundle_id" not in payload


def test_get_context_bundle_live_serves_without_alt_request(
    config, conn, mock_live_ingest_ok
) -> None:
    """Live bundle without alt symbols runs ingest then serves fresh bundle data."""
    import json

    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "2026-05-21T12:00:00+00:00",
            1000.0,
            0.0,
            json.dumps({"BTC": 0.7, "ETH": 0.3, "CASH": 0.0}),
            "{}",
        ),
    )
    conn.commit()
    payload = get_context_bundle(conn, config, scope="daily", freshness="live")

    assert payload.get("available") is not False
    assert payload["freshness"] == "live"
    assert payload["ingest"]["ok"] is True
    assert "bundle_id" in payload


def test_run_ingest_saves_snapshots(config, conn, monkeypatch) -> None:
    monkeypatch.setenv("KRAKEN_API_KEY", "test-key")
    monkeypatch.setenv("KRAKEN_API_SECRET", "dGVzdA==")
    with patch(
        "alloccontext.ingest.runner.refresh_fear_greed",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_kraken",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_kalshi",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_macro_calendar",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_etf_flows",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_coingecko",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_coinmarketcap",
        return_value={"ok": True, "rows": 0, "skipped": True},
    ), patch(
        "alloccontext.ingest.runner.refresh_fred",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_onchain_cycle",
        return_value={"ok": True, "rows": 14},
    ):
        from alloccontext.ingest.runner import run_ingest

        result = run_ingest(conn, config)

    assert "daily" in result["snapshots"]
    assert "weekly" in result["snapshots"]
    count = conn.execute("SELECT COUNT(*) FROM context_snapshots").fetchone()[0]
    assert count == 2
