from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from alloccontext.ingest.exchange_http import should_retry_exchange_attempt
from alloccontext.ingest.fred import refresh_fred, upsert_fred_observations
from alloccontext.ingest.kraken_client import KrakenClient, KrakenError
from alloccontext.rollup.context import build_context_bundle
from alloccontext.store.db import connect
from alloccontext.store.jsonutil import canonical_json
from alloccontext.store.retention import prune_to_horizon


def test_should_not_retry_http_401() -> None:
    response = MagicMock(status_code=401)
    exc = requests.HTTPError(response=response)
    assert should_retry_exchange_attempt(exc) is False


def test_kraken_client_does_not_retry_on_401() -> None:
    session = MagicMock()
    response = MagicMock(status_code=401)
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    session.get.return_value = response
    client = KrakenClient(max_retries=3, retry_backoff=0.0, session=session)
    with pytest.raises(KrakenError):
        client.get_ticker("XBTUSD")
    assert session.get.call_count == 1


def test_newer_database_schema_rejected() -> None:
    db_path = Path(tempfile.mkdtemp()) / "newer.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta VALUES ('version', '999');
        """
    )
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="newer than supported"):
        connect(db_path)


def test_prune_drops_old_ingest_runs(conn, config) -> None:
    conn.execute(
        """
        INSERT INTO ingest_runs(source, started_at, finished_at, rows_upserted)
        VALUES ('fred', '2020-01-01T00:00:00+00:00', '2020-01-01T00:01:00+00:00', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO ingest_runs(source, started_at, finished_at, rows_upserted)
        VALUES ('fred', '2026-05-21T12:00:00+00:00', '2026-05-21T12:01:00+00:00', 1)
        """
    )
    conn.commit()
    deleted = prune_to_horizon(conn, config)
    assert deleted["ingest_runs"] >= 1
    remaining = conn.execute("SELECT COUNT(*) AS n FROM ingest_runs").fetchone()
    assert remaining["n"] == 1


def test_context_snapshot_uses_canonical_json(conn, config) -> None:
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
    build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        as_of=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
        save_snapshot=True,
    )
    row = conn.execute(
        "SELECT context_json FROM context_snapshots WHERE scope = 'daily'"
    ).fetchone()
    assert row is not None
    assert row["context_json"] == canonical_json(json.loads(row["context_json"]))


def test_refresh_fred_rolls_back_on_partial_failure(conn, config, monkeypatch) -> None:
    from alloccontext.config import FredConfig, FredSeriesSpec
    from dataclasses import replace

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    narrow_config = replace(
        config,
        fred=FredConfig(
            series=[
                FredSeriesSpec(id="DGS10", label="10Y", category="rates"),
                FredSeriesSpec(id="DGS2", label="2Y", category="rates"),
            ],
            lookback_days=30,
            timeout_seconds=5.0,
        ),
    )
    good_payload = json.dumps(
        {"observations": [{"date": "2026-05-20", "value": "4.25"}]}
    ).encode()

    class GoodResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return good_payload

    call_count = {"n": 0}

    def fake_urlopen(request, timeout=30):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return GoodResponse()
        raise ValueError("fred series unavailable")

    monkeypatch.setattr(
        "alloccontext.ingest.fred.urllib.request.urlopen",
        fake_urlopen,
    )
    result = refresh_fred(conn, narrow_config)
    assert result["ok"] is False
    count = conn.execute("SELECT COUNT(*) AS n FROM fred_observations").fetchone()
    assert count["n"] == 0


def test_upsert_fred_observations_requires_refresh_commit(conn) -> None:
    upsert_fred_observations(
        conn,
        series_id="DGS10",
        observations=[{"date": "2026-05-20", "value": "4.25"}],
    )
    conn.commit()
    row = conn.execute(
        "SELECT value FROM fred_observations WHERE series_id = ?",
        ("DGS10",),
    ).fetchone()
    assert row["value"] == 4.25
