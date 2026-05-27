from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from alloccontext.timeutil import utc_now


def parse_as_of(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def age_seconds(as_of: datetime, *, now: datetime | None = None) -> int:
    ref = now or utc_now()
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return max(0, int((ref - as_of).total_seconds()))


def with_staleness(payload: dict[str, Any], *, as_of: datetime) -> dict[str, Any]:
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return {
        "as_of": as_of.replace(microsecond=0).isoformat(),
        "age_seconds": age_seconds(as_of),
        **payload,
    }
