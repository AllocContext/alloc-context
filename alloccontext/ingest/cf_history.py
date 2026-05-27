from __future__ import annotations

import datetime as dt
import json
import sqlite3
from typing import Any

from alloccontext.store.meta import get_meta, set_meta

CF_HISTORY_META_KEY = "cf_price_history"


def _parse_ts(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def load_cf_history(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    raw = get_meta(conn, CF_HISTORY_META_KEY)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        str(key): [row for row in rows if isinstance(row, dict)]
        for key, rows in parsed.items()
        if isinstance(rows, list)
    }


def save_cf_history(conn: sqlite3.Connection, history: dict[str, list[dict[str, Any]]]) -> None:
    set_meta(conn, CF_HISTORY_META_KEY, json.dumps(history))


def record_cf_price_samples(
    history: dict[str, list[dict[str, Any]]] | None,
    prices: dict[str, float],
    now: dt.datetime,
    *,
    max_age_minutes: float,
) -> dict[str, list[dict[str, Any]]]:
    out = {key: list(rows) for key, rows in (history or {}).items()}
    cutoff = now.astimezone(dt.timezone.utc) - dt.timedelta(minutes=max_age_minutes)
    stamp = now.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()
    for index, price in prices.items():
        rows = list(out.get(index) or [])
        rows.append({"at": stamp, "price": float(price)})
        kept: list[dict[str, Any]] = []
        for row in rows:
            ts = _parse_ts(row.get("at"))
            if ts is not None and ts >= cutoff:
                kept.append(row)
        out[index] = kept
    return out
