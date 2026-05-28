from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from alloccontext.ingest.macro_calendar import (
    fetch_finnhub_events,
    load_static_events,
    merge_events,
    refresh_macro_calendar,
)
from alloccontext.ingest.macro_normalize import (
    calendar_row_date_time,
    impact_meets_minimum,
    parse_event_ts,
)
from alloccontext.rollup.context import build_context_bundle
from alloccontext.rollup.macro import build_macro_context


def test_parse_event_ts_us_eastern() -> None:
    ts = parse_event_ts(
        date="2026-05-13",
        time="08:30",
        tz_name="America/New_York",
    )
    assert ts.endswith("+00:00")
    dt = datetime.fromisoformat(ts)
    assert dt.hour in (12, 13)  # EDT vs EST


def test_impact_filter() -> None:
    assert impact_meets_minimum("high", "medium") is True
    assert impact_meets_minimum("low", "medium") is False


def test_calendar_row_date_time_combined_finnhub_time() -> None:
    when = calendar_row_date_time(
        {
            "country": "US",
            "event": "Building Permits Prel",
            "time": "2026-05-21 12:30:00",
        }
    )
    assert when == ("2026-05-21", "12:30:00")


def test_calendar_row_date_time_separate_date_and_time() -> None:
    when = calendar_row_date_time(
        {"date": "2026-05-13", "time": "08:30:00"},
    )
    assert when == ("2026-05-13", "08:30:00")


def test_load_static_fomc_events() -> None:
    rows = load_static_events(
        Path("config/macro-calendar.yaml"),
        countries={"US"},
        min_impact="high",
    )
    assert len(rows) >= 8
    assert all(row["source"] == "static" for row in rows)
    assert any("FOMC" in row["name"] for row in rows)


def test_fetch_finnhub_from_fixture(monkeypatch) -> None:
    payload = json.loads(
        Path("tests/fixtures/finnhub_economic_calendar.json").read_text()
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(
        "alloccontext.ingest.macro_calendar.urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )
    rows = fetch_finnhub_events(
        start=datetime(2026, 5, 1, tzinfo=timezone.utc).date(),
        end=datetime(2026, 6, 30, tzinfo=timezone.utc).date(),
        api_key="test",
        countries={"US"},
        min_impact="medium",
    )
    assert len(rows) == 2
    assert rows[0]["name"].startswith("Consumer Price Index")


def test_fetch_finnhub_combined_time_field(monkeypatch) -> None:
    payload = {
        "economicCalendar": [
            {
                "country": "US",
                "event": "Building Permits Prel",
                "impact": "high",
                "time": "2026-05-21 12:30:00",
                "actual": 1.442,
                "estimate": 1.39,
                "prev": 1.363,
            },
            {
                "country": "US",
                "event": "Weekly Claim",
                "impact": "low",
                "time": "2026-05-22 08:30:00",
            },
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr(
        "alloccontext.ingest.macro_calendar.urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )
    rows = fetch_finnhub_events(
        start=datetime(2026, 5, 1, tzinfo=timezone.utc).date(),
        end=datetime(2026, 6, 30, tzinfo=timezone.utc).date(),
        api_key="test",
        countries={"US"},
        min_impact="medium",
    )
    assert len(rows) == 1
    assert rows[0]["name"] == "Building Permits Prel"
    assert rows[0]["source"] == "finnhub"
    assert rows[0]["event_ts"].startswith("2026-05-21")


def test_merge_prefers_static_over_api() -> None:
    static = [
        {
            "event_id": "static:2026-06-17:fomc",
            "event_ts": "2026-06-17T18:00:00+00:00",
            "country": "US",
            "name": "FOMC statement",
            "impact": "high",
            "category": "monetary",
            "source": "static",
            "raw": {},
        }
    ]
    api = [
        {
            "event_id": "finnhub:2026-06-17:fomc",
            "event_ts": "2026-06-17T18:00:00+00:00",
            "country": "US",
            "name": "FOMC statement",
            "impact": "high",
            "category": "economic",
            "source": "finnhub",
            "raw": {},
        }
    ]
    merged = merge_events(static, api)
    assert len(merged) == 1
    assert merged[0]["source"] == "static"


def test_refresh_macro_calendar_static_only(conn, config) -> None:
    result = refresh_macro_calendar(conn, config)
    assert result["ok"] is True
    assert result["rows"] >= 8
    assert "static" in result["sources"]


def test_build_macro_context_daily(conn, config) -> None:
    refresh_macro_calendar(conn, config)
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    ctx = build_macro_context(conn, config, now=now, scope="daily")
    assert ctx["available"] is True
    assert "past_24h" in ctx["events"]
    assert "next_7d" in ctx["events"]
    upcoming = ctx["events"]["next_7d"]
    assert any("FOMC" in event["name"] for event in upcoming)


def test_context_bundle_includes_macro(conn, config) -> None:
    refresh_macro_calendar(conn, config)
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    bundle = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        as_of=now,
    )
    assert bundle["macro"]["available"] is True
    assert bundle["macro"]["events"]["next_7d"]
