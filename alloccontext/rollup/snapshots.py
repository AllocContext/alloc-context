from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal

Scope = Literal["daily", "weekly"]


class SnapshotNotFoundError(LookupError):
    pass


def load_context_bundle_snapshot(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    as_of: str,
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT context_json FROM context_snapshots
        WHERE scope = ? AND as_of = ?
        """,
        (scope, as_of),
    ).fetchone()
    if row is None:
        raise SnapshotNotFoundError(f"no {scope} snapshot at {as_of}")
    try:
        return json.loads(row["context_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise SnapshotNotFoundError(f"invalid snapshot JSON at {as_of}") from exc


def resolve_context_snapshot_as_of(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    as_of: str,
    mode: Literal["exact", "at_or_before"] = "exact",
) -> str:
    if mode == "exact":
        row = conn.execute(
            """
            SELECT as_of FROM context_snapshots
            WHERE scope = ? AND as_of = ?
            """,
            (scope, as_of),
        ).fetchone()
        if row is None:
            raise SnapshotNotFoundError(f"no {scope} snapshot at {as_of}")
        return str(row["as_of"])

    row = conn.execute(
        """
        SELECT as_of FROM context_snapshots
        WHERE scope = ? AND as_of <= ?
        ORDER BY as_of DESC LIMIT 1
        """,
        (scope, as_of),
    ).fetchone()
    if row is None:
        raise SnapshotNotFoundError(f"no {scope} snapshot at or before {as_of}")
    return str(row["as_of"])
