from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal

Scope = Literal["daily", "weekly"]
BaselineMode = Literal["at_or_before", "earliest_available", "missing"]
MAX_REPLAY_CHECKPOINTS = 31


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


def resolve_thesis_baseline_as_of(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    recorded_at: str,
) -> tuple[str | None, BaselineMode]:
    """Resolve thesis baseline: at-or-before recorded_at, else earliest snapshot."""
    row = conn.execute(
        """
        SELECT as_of FROM context_snapshots
        WHERE scope = ? AND as_of <= ?
        ORDER BY as_of DESC LIMIT 1
        """,
        (scope, recorded_at),
    ).fetchone()
    if row is not None:
        return str(row["as_of"]), "at_or_before"

    row = conn.execute(
        """
        SELECT as_of FROM context_snapshots
        WHERE scope = ?
        ORDER BY as_of ASC LIMIT 1
        """,
        (scope,),
    ).fetchone()
    if row is not None:
        return str(row["as_of"]), "earliest_available"
    return None, "missing"


def _subsample_evenly(values: list[str], limit: int) -> list[str]:
    if len(values) <= limit:
        return values
    if limit <= 1:
        return [values[-1]]
    step = (len(values) - 1) / (limit - 1)
    picked: list[str] = []
    for index in range(limit):
        picked.append(values[min(int(round(index * step)), len(values) - 1)])
    deduped: list[str] = []
    seen: set[str] = set()
    for value in picked:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def list_context_snapshot_as_ofs_between(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    after_exclusive: str,
    through_inclusive: str,
    limit: int = MAX_REPLAY_CHECKPOINTS,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT as_of FROM context_snapshots
        WHERE scope = ? AND as_of > ? AND as_of <= ?
        ORDER BY as_of ASC
        """,
        (scope, after_exclusive, through_inclusive),
    ).fetchall()
    values = [str(row["as_of"]) for row in rows]
    return _subsample_evenly(values, limit)
