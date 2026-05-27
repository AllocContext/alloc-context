from __future__ import annotations

import sqlite3
from typing import Any


def _source_health(last_by_source: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    health: dict[str, dict[str, Any]] = {}
    for source, row in last_by_source.items():
        error = row.get("error")
        health[source] = {
            "ok": error is None,
            "finished_at": row.get("finished_at"),
            "rows_upserted": row.get("rows_upserted"),
            "error": error,
        }
    return health


def ingest_status(conn: sqlite3.Connection) -> dict[str, Any]:
    fg = conn.execute(
        """
        SELECT ts, value, classification, fetched_at
        FROM fear_greed ORDER BY CAST(ts AS INTEGER) DESC LIMIT 1
        """
    ).fetchone()
    portfolio = conn.execute(
        """
        SELECT ts, nav_usd, cash_usd, allocation_json
        FROM portfolio_snapshots ORDER BY ts DESC LIMIT 1
        """
    ).fetchone()
    bars = conn.execute(
        """
        SELECT pair, interval_minutes, MAX(bar_ts) AS latest_bar_ts, COUNT(*) AS bar_count
        FROM market_bars
        GROUP BY pair, interval_minutes
        ORDER BY pair
        """
    ).fetchall()
    recent_ingest = conn.execute(
        """
        SELECT source, started_at, finished_at, rows_upserted, error
        FROM ingest_runs ORDER BY id DESC LIMIT 20
        """
    ).fetchall()
    last_by_source: dict[str, dict[str, Any]] = {}
    for row in recent_ingest:
        source = str(row["source"])
        if source not in last_by_source:
            last_by_source[source] = dict(row)

    return {
        "fear_greed_latest": dict(fg) if fg else None,
        "portfolio_latest": dict(portfolio) if portfolio else None,
        "market_bars": [dict(row) for row in bars],
        "last_ingest_by_source": last_by_source,
        "source_health": _source_health(last_by_source),
        "recent_ingest": [dict(row) for row in recent_ingest[:10]],
    }
