from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from typing import Any

from alloccontext.timeutil import utc_now_iso

FNG_API = "https://api.alternative.me/fng/"


def classify_fear_greed(value: int) -> str:
    if value <= 24:
        return "Extreme Fear"
    if value <= 44:
        return "Fear"
    if value <= 55:
        return "Neutral"
    if value <= 74:
        return "Greed"
    return "Extreme Greed"


def _parse_row(row: dict[str, Any]) -> dict[str, Any]:
    value = int(row["value"])
    ts = int(row["timestamp"])
    return {
        "timestamp": ts,
        "value": value,
        "classification": classify_fear_greed(value),
    }


def fetch_fear_greed(*, limit: int = 1, timeout: float = 15.0) -> list[dict[str, Any]]:
    """Fetch Crypto Fear & Greed Index rows from alternative.me."""
    url = f"{FNG_API}?limit={max(1, limit)}"
    req = urllib.request.Request(url, headers={"User-Agent": "alloc-context/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    if not isinstance(payload, dict):
        raise ValueError("invalid fear_greed payload")
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise ValueError("invalid fear_greed data")
    return [_parse_row(row) for row in rows if isinstance(row, dict)]


def upsert_fear_greed_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    fetched_at = utc_now_iso()
    count = 0
    for row in rows:
        conn.execute(
            """
            INSERT INTO fear_greed(ts, value, classification, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ts) DO UPDATE SET
              value=excluded.value,
              classification=excluded.classification,
              fetched_at=excluded.fetched_at
            """,
            (
                str(int(row["timestamp"])),
                int(row["value"]),
                str(row["classification"]),
                fetched_at,
            ),
        )
        count += 1
    return count


def refresh_fear_greed(
    conn: sqlite3.Connection,
    *,
    history_limit: int = 90,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Refresh recent F&G history into SQLite."""
    try:
        rows = fetch_fear_greed(limit=history_limit, timeout=timeout)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        conn.rollback()
        return {"ok": False, "error": str(exc), "rows": 0}
    if not rows:
        return {"ok": False, "error": "empty_response", "rows": 0}
    upserted = upsert_fear_greed_rows(conn, rows)
    conn.commit()
    return {"ok": True, "rows": upserted, "latest": rows[0]}
