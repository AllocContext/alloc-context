from __future__ import annotations

import json

from alloccontext.mcp.handlers import get_context_at, get_context_delta
from alloccontext.rollup.comparison import compare_context_bundles
from alloccontext.rollup.context import build_context_bundle
from alloccontext.rollup.snapshots import SnapshotNotFoundError


def _save_snapshot(conn, scope: str, as_of: str, bundle: dict) -> None:
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        VALUES (?, ?, ?)
        ON CONFLICT(scope, as_of) DO UPDATE SET context_json = excluded.context_json
        """,
        (scope, as_of, json.dumps(bundle)),
    )
    conn.commit()


def test_get_context_at_loads_snapshot(conn, config) -> None:
    bundle = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=True,
    )
    loaded = get_context_at(
        conn,
        config,
        scope="daily",
        as_of=bundle["as_of"],
        match="exact",
    )
    assert loaded["as_of"] == bundle["as_of"]
    assert loaded["regime"]["risk_off"]["level"] in ("low", "moderate", "high")


def test_get_context_at_missing_raises(conn, config) -> None:
    try:
        get_context_at(
            conn,
            config,
            scope="daily",
            as_of="1999-01-01T00:00:00+00:00",
            match="exact",
        )
    except SnapshotNotFoundError:
        return
    raise AssertionError("expected SnapshotNotFoundError")


def test_get_context_delta_between_snapshots(conn, config) -> None:
    first = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=True,
    )
    second = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=True,
    )
    delta = get_context_delta(
        conn,
        config,
        scope="daily",
        prior_as_of=first["as_of"],
        current_as_of=second["as_of"],
    )
    assert delta["prior_snapshot_as_of"] == first["as_of"]
    assert delta["current_snapshot_as_of"] == second["as_of"]
    assert "notable_shifts" in delta


def test_compare_context_bundles_fear_greed_shift() -> None:
    prior = {
        "as_of": "2026-05-20T12:00:00+00:00",
        "portfolio": {"available": True, "allocation_pct": {"BTC": 0.7, "ETH": 0.3, "CASH": 0.0}},
        "sentiment": {"available": True, "fear_greed": {"value": 30}},
        "delta": {"available": True, "notable_shifts": []},
    }
    current = {
        "as_of": "2026-05-21T12:00:00+00:00",
        "portfolio": {"available": True, "allocation_pct": {"BTC": 0.65, "ETH": 0.35, "CASH": 0.0}},
        "sentiment": {"available": True, "fear_greed": {"value": 20}},
        "delta": {"available": True, "notable_shifts": []},
    }
    diff = compare_context_bundles(prior, current)
    assert any("F&G" in line for line in diff["notable_shifts"])
    assert diff["fear_greed_change"] == -10
