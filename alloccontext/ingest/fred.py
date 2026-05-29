from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any

from alloccontext.timeutil import utc_now_iso

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series_observations(
    *,
    series_id: str,
    api_key: str,
    observation_start: date,
    observation_end: date,
    timeout: float,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": observation_start.isoformat(),
            "observation_end": observation_end.isoformat(),
            "sort_order": "asc",
        }
    )
    url = f"{FRED_OBSERVATIONS_URL}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "alloc-context/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        from alloccontext.ingest.http_errors import http_error_message

        raise ValueError(
            http_error_message(exc, context=f"fred series {series_id}")
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid FRED payload for {series_id}")
    rows = payload.get("observations") or []
    if not isinstance(rows, list):
        raise ValueError(f"invalid FRED observations for {series_id}")
    return [row for row in rows if isinstance(row, dict)]


def _parse_observation(row: dict[str, Any]) -> tuple[str, float | None] | None:
    obs_date = str(row.get("date") or "").strip()
    if not obs_date:
        return None
    raw_value = row.get("value")
    if raw_value is None or raw_value == ".":
        return obs_date, None
    try:
        return obs_date, float(raw_value)
    except (TypeError, ValueError):
        return obs_date, None


def upsert_fred_observations(
    conn: sqlite3.Connection,
    *,
    series_id: str,
    observations: list[dict[str, Any]],
) -> int:
    fetched_at = utc_now_iso()
    count = 0
    for row in observations:
        parsed = _parse_observation(row)
        if parsed is None:
            continue
        obs_date, value = parsed
        conn.execute(
            """
            INSERT INTO fred_observations(series_id, obs_date, value, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(series_id, obs_date) DO UPDATE SET
              value=excluded.value,
              fetched_at=excluded.fetched_at
            """,
            (series_id, obs_date, value, fetched_at),
        )
        count += 1
    return count


def refresh_fred(conn: sqlite3.Connection, config) -> dict[str, Any]:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return {
            "ok": True,
            "rows": 0,
            "skipped": True,
            "reason": "FRED_API_KEY not set",
        }

    fred = config.fred
    if not fred.series:
        return {
            "ok": True,
            "rows": 0,
            "skipped": True,
            "reason": "no_fred_series_configured",
        }

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=fred.lookback_days)
    total = 0
    series_ids: list[str] = []

    for spec in fred.series:
        try:
            observations = fetch_series_observations(
                series_id=spec.id,
                api_key=api_key,
                observation_start=start,
                observation_end=today,
                timeout=fred.timeout_seconds,
            )
            total += upsert_fred_observations(conn, series_id=spec.id, observations=observations)
            series_ids.append(spec.id)
        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
            RuntimeError,
        ) as exc:
            conn.rollback()
            return {"ok": False, "error": f"{spec.id}: {exc}", "rows": 0}

    conn.commit()
    return {"ok": True, "rows": total, "series": series_ids}
