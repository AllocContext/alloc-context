from __future__ import annotations

import sqlite3
from typing import Any, Literal

from alloccontext.predictions.extract import ForwardWatch
from alloccontext.timeutil import utc_now_iso

PredictionStatus = Literal["open", "hit", "miss", "partial", "expired"]


def _watch_key(watch: ForwardWatch) -> tuple[str, str]:
    return watch.condition_text, watch.watch_text


def save_predictions(
    conn: sqlite3.Connection,
    *,
    scope: str,
    brief_as_of: str,
    watches: list[ForwardWatch],
) -> int:
    """Upsert predictions for a brief; preserve reviewed statuses."""
    existing_rows = conn.execute(
        """
        SELECT id, condition_text, watch_text, by_text, status,
               reviewed_at, outcome_notes, created_at
        FROM brief_predictions
        WHERE scope = ? AND brief_as_of = ?
        """,
        (scope, brief_as_of),
    ).fetchall()
    existing = {
        (str(row["condition_text"]), str(row["watch_text"])): dict(row)
        for row in existing_rows
    }
    incoming_keys = {_watch_key(watch) for watch in watches}
    created_at = utc_now_iso()
    saved = 0

    for watch in watches:
        key = _watch_key(watch)
        prior = existing.get(key)
        if prior is None:
            conn.execute(
                """
                INSERT INTO brief_predictions(
                  scope, brief_as_of, condition_text, watch_text, by_text,
                  created_at, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'open')
                """,
                (
                    scope,
                    brief_as_of,
                    watch.condition_text,
                    watch.watch_text,
                    watch.by_text,
                    created_at,
                ),
            )
            saved += 1
            continue

        if prior["status"] != "open":
            if watch.by_text and watch.by_text != prior.get("by_text"):
                conn.execute(
                    """
                    UPDATE brief_predictions SET by_text = ?
                    WHERE id = ?
                    """,
                    (watch.by_text, prior["id"]),
                )
            saved += 1
            continue

        conn.execute(
            """
            UPDATE brief_predictions
            SET by_text = ?, condition_text = ?, watch_text = ?
            WHERE id = ?
            """,
            (watch.by_text, watch.condition_text, watch.watch_text, prior["id"]),
        )
        saved += 1

    for key, prior in existing.items():
        if key not in incoming_keys and prior["status"] == "open":
            conn.execute("DELETE FROM brief_predictions WHERE id = ?", (prior["id"],))

    return saved


def list_predictions(
    conn: sqlite3.Connection,
    *,
    month: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT id, scope, brief_as_of, condition_text, watch_text, by_text,
               created_at, status, reviewed_at, outcome_notes
        FROM brief_predictions
    """
    clauses: list[str] = []
    params: list[Any] = []
    if month:
        clauses.append("strftime('%Y-%m', brief_as_of) = ?")
        params.append(month)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY brief_as_of DESC, id ASC"
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def update_prediction_status(
    conn: sqlite3.Connection,
    prediction_id: int,
    *,
    status: PredictionStatus,
    outcome_notes: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE brief_predictions
        SET status = ?, reviewed_at = ?, outcome_notes = ?
        WHERE id = ?
        """,
        (status, utc_now_iso(), outcome_notes, prediction_id),
    )
