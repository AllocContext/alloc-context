from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from alloccontext.ingest.fred import (
    fetch_series_observations,
    refresh_fred,
    upsert_fred_observations,
)
from alloccontext.rollup.context import build_context_bundle
from alloccontext.rollup.macro import build_macro_context


def test_fetch_fred_from_fixture(monkeypatch) -> None:
    payload = json.loads(
        Path("tests/fixtures/fred_dgs10_observations.json").read_text()
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(
        "alloccontext.ingest.fred.urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )
    rows = fetch_series_observations(
        series_id="DGS10",
        api_key="test",
        observation_start=datetime(2026, 2, 1, tzinfo=timezone.utc).date(),
        observation_end=datetime(2026, 5, 21, tzinfo=timezone.utc).date(),
        timeout=5.0,
    )
    assert len(rows) == 4
    assert rows[-1]["value"] == "4.25"


def test_refresh_fred_skips_without_key(conn, config, monkeypatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    result = refresh_fred(conn, config)
    assert result["ok"] is True
    assert result["skipped"] is True


def test_refresh_fred_upserts(conn, config, monkeypatch) -> None:
    payload = json.loads(
        Path("tests/fixtures/fred_dgs10_observations.json").read_text()
    )
    monkeypatch.setenv("FRED_API_KEY", "test-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(
        "alloccontext.ingest.fred.urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    # Only fetch DGS10 in this test to limit mock calls.
    from alloccontext.config import FredConfig, FredSeriesSpec

    narrow_config = replace(
        config,
        fred=FredConfig(
            series=[FredSeriesSpec(id="DGS10", label="10Y", category="rates")],
            lookback_days=120,
            timeout_seconds=5.0,
        ),
    )

    result = refresh_fred(conn, narrow_config)
    assert result["ok"] is True
    assert result["rows"] == 4

    row = conn.execute(
        "SELECT value FROM fred_observations WHERE series_id = ? AND obs_date = ?",
        ("DGS10", "2026-05-20"),
    ).fetchone()
    assert row["value"] == 4.25


def test_build_macro_indicators(conn, config) -> None:
    upsert_fred_observations(
        conn,
        series_id="DGS10",
        observations=[
            {"date": "2026-02-20", "value": "4.10"},
            {"date": "2026-04-20", "value": "4.20"},
            {"date": "2026-05-14", "value": "4.30"},
            {"date": "2026-05-20", "value": "4.25"},
        ],
    )
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    ctx = build_macro_context(conn, config, now=now, scope="daily")
    assert ctx["available"] is True
    assert "indicators" in ctx
    dgs10 = ctx["indicators"]["DGS10"]
    assert dgs10["value"] == 4.25
    assert dgs10["change_7d"] == -0.05
    assert dgs10["change_30d"] == 0.05


def test_context_bundle_includes_fred_indicators(conn, config) -> None:
    upsert_fred_observations(
        conn,
        series_id="DGS10",
        observations=[{"date": "2026-05-20", "value": "4.25"}],
    )
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    bundle = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        as_of=now,
    )
    assert bundle["macro"]["available"] is True
    assert "DGS10" in bundle["macro"]["indicators"]
