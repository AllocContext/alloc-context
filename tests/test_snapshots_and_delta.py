from __future__ import annotations

import json

from alloccontext.mcp.handlers import get_context_at, get_context_delta
from alloccontext.rollup.comparison import compare_context_bundles
from alloccontext.rollup.context import build_context_bundle
from alloccontext.rollup.snapshots import (
    list_context_snapshot_as_ofs_between,
    resolve_thesis_baseline_as_of,
)


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


def test_get_context_at_missing_returns_unavailable(conn, config) -> None:
    loaded = get_context_at(
        conn,
        config,
        scope="daily",
        as_of="1999-01-01T00:00:00+00:00",
        match="exact",
    )
    assert loaded["available"] is False
    assert "1999-01-01" in loaded["reason"]


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
    assert any("BTC allocation" in line for line in diff["sleeve_shifts"])
    assert not any("allocation" in line for line in diff["market_shifts"])
    assert diff["fear_greed_change"] == -10


def test_resolve_thesis_baseline_earliest_available(conn, config) -> None:
    bundle = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=False,
    )
    bundle["as_of"] = "2026-06-10T12:00:00+00:00"
    _save_snapshot(conn, "daily", bundle["as_of"], bundle)

    resolved, mode = resolve_thesis_baseline_as_of(
        conn,
        scope="daily",
        recorded_at="2026-06-01T00:00:00Z",
    )
    assert mode == "earliest_available"
    assert resolved == "2026-06-10T12:00:00+00:00"


def test_list_context_snapshot_as_ofs_between_subsamples(conn, config) -> None:
    for day in range(1, 12):
        bundle = {"as_of": f"2026-06-{day:02d}T12:00:00+00:00"}
        _save_snapshot(conn, "daily", bundle["as_of"], bundle)

    as_ofs = list_context_snapshot_as_ofs_between(
        conn,
        scope="daily",
        after_exclusive="2026-06-01T12:00:00+00:00",
        through_inclusive="2026-06-11T12:00:00+00:00",
        limit=5,
    )
    assert len(as_ofs) == 5
    assert as_ofs[0] == "2026-06-02T12:00:00+00:00"
    assert as_ofs[-1] == "2026-06-11T12:00:00+00:00"
