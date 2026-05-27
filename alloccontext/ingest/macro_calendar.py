from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from alloccontext.ingest.macro_normalize import (
    impact_meets_minimum,
    normalize_impact,
    normalized_event,
    parse_event_ts,
)

FINNHUB_URL = "https://finnhub.io/api/v1/calendar/economic"
FMP_URL = "https://financialmodelingprep.com/stable/economic-calendar"


def load_static_events(path: Path, *, countries: set[str], min_impact: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text()) or {}
    tz_name = str(raw.get("timezone") or "America/New_York")
    rows: list[dict[str, Any]] = []
    for item in raw.get("events") or []:
        if not isinstance(item, dict):
            continue
        country = str(item.get("country") or "US").upper()
        if countries and country not in countries:
            continue
        impact = normalize_impact(str(item.get("impact") or "high"))
        if not impact_meets_minimum(impact, min_impact):
            continue
        event_date = str(item.get("date") or "").strip()
        if not event_date:
            continue
        event_ts = parse_event_ts(
            date=event_date,
            time=str(item.get("time") or "00:00"),
            tz_name=tz_name,
        )
        rows.append(
            normalized_event(
                source="static",
                country=country,
                name=str(item.get("name") or "Macro event"),
                event_ts=event_ts,
                impact=impact,
                category=str(item.get("category") or "macro"),
                raw=dict(item),
            )
        )
    return rows


def fetch_finnhub_events(
    *,
    start: date,
    end: date,
    api_key: str,
    countries: set[str],
    min_impact: str,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    url = (
        f"{FINNHUB_URL}?from={start.isoformat()}&to={end.isoformat()}"
        f"&token={api_key}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "alloc-context/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    calendar = payload.get("economicCalendar") if isinstance(payload, dict) else payload
    if not isinstance(calendar, list):
        raise ValueError("invalid finnhub economic calendar payload")

    rows: list[dict[str, Any]] = []
    for item in calendar:
        if not isinstance(item, dict):
            continue
        country = str(item.get("country") or "").upper()
        if countries and country not in countries:
            continue
        impact = normalize_impact(str(item.get("impact") or "medium"))
        if not impact_meets_minimum(impact, min_impact):
            continue
        event_date = str(item.get("date") or "").strip()
        if not event_date:
            continue
        event_ts = parse_event_ts(
            date=event_date,
            time=str(item.get("time") or "00:00:00"),
            tz_name="America/New_York",
        )
        rows.append(
            normalized_event(
                source="finnhub",
                country=country or "US",
                name=str(item.get("event") or "Economic release"),
                event_ts=event_ts,
                impact=impact,
                category="economic",
                actual=item.get("actual"),
                estimate=item.get("estimate"),
                previous=item.get("prev"),
                unit=item.get("unit"),
                raw=item,
            )
        )
    return rows


def fetch_fmp_events(
    *,
    start: date,
    end: date,
    api_key: str,
    countries: set[str],
    min_impact: str,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    url = (
        f"{FMP_URL}?from={start.isoformat()}&to={end.isoformat()}"
        f"&apikey={api_key}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "alloc-context/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    if not isinstance(payload, list):
        raise ValueError("invalid fmp economic calendar payload")

    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        country = str(item.get("country") or item.get("currency") or "US").upper()
        if len(country) == 3 and country in {"USD", "EUR", "GBP"}:
            country = {"USD": "US", "EUR": "EU", "GBP": "UK"}.get(country, country)
        if countries and country not in countries:
            continue
        impact = normalize_impact(str(item.get("impact") or item.get("importance") or "medium"))
        if not impact_meets_minimum(impact, min_impact):
            continue
        event_date = str(item.get("date") or "").strip()[:10]
        if not event_date:
            continue
        event_ts = parse_event_ts(
            date=event_date,
            time=str(item.get("time") or item.get("releaseTime") or "00:00:00"),
            tz_name="America/New_York",
        )
        rows.append(
            normalized_event(
                source="fmp",
                country=country or "US",
                name=str(item.get("event") or item.get("name") or "Economic release"),
                event_ts=event_ts,
                impact=impact,
                category="economic",
                actual=item.get("actual"),
                estimate=item.get("estimate") or item.get("forecast"),
                previous=item.get("previous") or item.get("prior"),
                unit=item.get("unit"),
                raw=item,
            )
        )
    return rows


def merge_events(*feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer earlier feeds on duplicate day+name (static wins over API)."""
    merged: dict[str, dict[str, Any]] = {}
    for feed in feeds:
        for event in feed:
            key = f"{event['event_ts'][:10]}:{event['name'].lower()}"
            if key not in merged:
                merged[key] = event
    return sorted(merged.values(), key=lambda row: row["event_ts"])


def upsert_macro_events(conn: sqlite3.Connection, events: list[dict[str, Any]]) -> int:
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    count = 0
    for event in events:
        conn.execute(
            """
            INSERT INTO macro_events(
              event_id, event_ts, country, name, impact, category,
              actual, estimate, previous, unit, source, raw_json, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
              event_ts = excluded.event_ts,
              country = excluded.country,
              name = excluded.name,
              impact = excluded.impact,
              category = excluded.category,
              actual = excluded.actual,
              estimate = excluded.estimate,
              previous = excluded.previous,
              unit = excluded.unit,
              source = excluded.source,
              raw_json = excluded.raw_json,
              fetched_at = excluded.fetched_at
            """,
            (
                event["event_id"],
                event["event_ts"],
                event["country"],
                event["name"],
                event["impact"],
                event.get("category"),
                _json_scalar(event.get("actual")),
                _json_scalar(event.get("estimate")),
                _json_scalar(event.get("previous")),
                event.get("unit"),
                event["source"],
                json.dumps(event.get("raw") or {}),
                fetched_at,
            ),
        )
        count += 1
    conn.commit()
    return count


def _json_scalar(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def refresh_macro_calendar(conn: sqlite3.Connection, config) -> dict[str, Any]:
    macro = config.macro
    countries = {c.upper() for c in macro.countries}
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=macro.fetch_past_days)
    end = today + timedelta(days=macro.fetch_future_days)

    feeds: list[list[dict[str, Any]]] = []
    feed_errors: dict[str, str] = {}

    static_path = Path(macro.static_calendar)
    static_rows = load_static_events(
        static_path, countries=countries, min_impact=macro.min_impact
    )
    feeds.append(static_rows)

    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    if macro.finnhub_enabled and finnhub_key:
        try:
            feeds.append(
                fetch_finnhub_events(
                    start=start,
                    end=end,
                    api_key=finnhub_key,
                    countries=countries,
                    min_impact=macro.min_impact,
                    timeout=macro.timeout_seconds,
                )
            )
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            feed_errors["finnhub"] = str(exc)

    fmp_key = os.environ.get("FMP_API_KEY")
    if macro.fmp_enabled and fmp_key:
        try:
            feeds.append(
                fetch_fmp_events(
                    start=start,
                    end=end,
                    api_key=fmp_key,
                    countries=countries,
                    min_impact=macro.min_impact,
                    timeout=macro.timeout_seconds,
                )
            )
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            feed_errors["fmp"] = str(exc)

    merged = merge_events(*feeds)
    upserted = upsert_macro_events(conn, merged)

    ok = upserted > 0 or bool(static_rows)
    return {
        "ok": ok,
        "rows": upserted,
        "static_rows": len(static_rows),
        "feed_errors": feed_errors,
        "sources": sorted({row["source"] for row in merged}),
    }
