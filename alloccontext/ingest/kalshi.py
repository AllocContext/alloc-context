from __future__ import annotations

import json
import sqlite3
from typing import Any

from alloccontext.ingest.kalshi_files import load_tactical_snapshot
from alloccontext.ingest.kalshi_state import (
    extract_cf_price_history,
    extract_market_quotes_from_state,
    load_state_json,
    tactical_to_storage,
)
from alloccontext.store.meta import set_meta


def upsert_kalshi_snapshot(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO kalshi_snapshots(ts, tape_summary, cluster_json, raw_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            str(row["ts"]),
            row.get("tape_summary"),
            row.get("cluster_json"),
            row.get("raw_json"),
        ),
    )


def _refresh_kalshi_files(conn: sqlite3.Connection, config) -> dict[str, Any]:
    tactical_path = config.kalshi.fallback_tactical_snapshot
    if tactical_path is None or not tactical_path.is_file():
        return {"ok": False, "error": "missing_kalshi_tactical_snapshot", "rows": 0}

    raw = load_state_json(tactical_path)
    if raw is None:
        return {"ok": False, "error": "invalid_tactical_snapshot", "rows": 0}

    snapshot = load_tactical_snapshot(tactical_path)
    if snapshot is None:
        return {"ok": False, "error": "invalid_tactical_snapshot", "rows": 0}

    storage = tactical_to_storage(snapshot, raw)
    upsert_kalshi_snapshot(conn, storage)

    state_path = config.kalshi.fallback_state
    if state_path is not None and state_path.is_file():
        state = load_state_json(state_path)
        if state:
            cf = extract_cf_price_history(state)
            if cf:
                set_meta(conn, "cf_price_history", json.dumps(cf))
            quotes = extract_market_quotes_from_state(state)
            if quotes:
                set_meta(conn, "kalshi_markets", json.dumps(quotes))

    conn.commit()
    return {
        "ok": True,
        "rows": 1,
        "ts": storage["ts"],
        "tape_summary": storage.get("tape_summary"),
        "source": "kalshi_files",
    }


def refresh_kalshi(conn: sqlite3.Connection, config) -> dict[str, Any]:
    if config.kalshi.use_api:
        from alloccontext.ingest.kalshi_api import refresh_kalshi_api

        result = refresh_kalshi_api(conn, config)
        if result.get("ok"):
            return result
        fallback = config.kalshi.fallback_tactical_snapshot
        if fallback is not None and fallback.is_file():
            file_result = _refresh_kalshi_files(conn, config)
            if file_result.get("ok"):
                file_result["api_error"] = result.get("error")
                return file_result
        return result

    return _refresh_kalshi_files(conn, config)
