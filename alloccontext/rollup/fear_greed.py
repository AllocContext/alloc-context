from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def _row_to_context(row: sqlite3.Row, *, now: datetime) -> dict[str, Any]:
    ts = int(row["ts"])
    computed_at = datetime.fromtimestamp(ts, tz=timezone.utc)
    age = max(0, int((now - computed_at).total_seconds()))
    return {
        "value": int(row["value"]),
        "classification": str(row["classification"]),
        "timestamp": ts,
        "computed_at": computed_at.replace(microsecond=0).isoformat(),
        "age_seconds": age,
    }


def build_fear_greed_context(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    max_age_seconds: int = 86_400 * 2,
) -> dict[str, Any] | None:
    now = now or datetime.now(timezone.utc)
    row = conn.execute(
        """
        SELECT ts, value, classification, fetched_at
        FROM fear_greed ORDER BY CAST(ts AS INTEGER) DESC LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    ctx = _row_to_context(row, now=now)
    if ctx["age_seconds"] > max_age_seconds:
        ctx["stale"] = True
    return ctx


def fear_greed_at_or_before(
    conn: sqlite3.Connection,
    *,
    at_ts: int,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT ts, value, classification, fetched_at
        FROM fear_greed
        WHERE CAST(ts AS INTEGER) <= ?
        ORDER BY CAST(ts AS INTEGER) DESC
        LIMIT 1
        """,
        (at_ts,),
    ).fetchone()
    if row is None:
        return None
    at = datetime.fromtimestamp(at_ts, tz=timezone.utc)
    return _row_to_context(row, now=at)
