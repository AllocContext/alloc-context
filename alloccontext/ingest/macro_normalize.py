from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

_IMPACT_RANK = {"low": 1, "medium": 2, "high": 3}


def normalize_impact(value: str | None) -> str:
    if not value:
        return "medium"
    cleaned = str(value).strip().lower()
    if cleaned in _IMPACT_RANK:
        return cleaned
    if cleaned in {"1", "2", "3"}:
        return {1: "low", 2: "medium", 3: "high"}[int(cleaned)]
    return "medium"


def impact_meets_minimum(impact: str, minimum: str) -> bool:
    return _IMPACT_RANK.get(impact, 2) >= _IMPACT_RANK.get(minimum, 2)


def slug_event_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] or "event"


def calendar_row_date_time(
    item: dict[str, Any],
    *,
    date_key: str = "date",
    time_key: str = "time",
) -> tuple[str, str] | None:
    """Extract (YYYY-MM-DD, HH:MM:SS) from calendar API rows.

    Finnhub live payloads often use a combined ``time`` field
    (``2026-05-21 12:30:00``) without a separate ``date`` key.
    """
    raw_date = str(item.get(date_key) or "").strip()
    raw_time = str(item.get(time_key) or "").strip()
    if raw_date:
        return raw_date[:10], raw_time or "00:00:00"
    if not raw_time:
        return None
    if " " in raw_time:
        date_part, clock = raw_time.split(" ", 1)
        return date_part.strip()[:10], clock.strip()
    return None


def parse_event_ts(
    *,
    date: str,
    time: str | None,
    tz_name: str,
) -> str:
    """Return UTC ISO timestamp for a calendar date + local time."""
    local_tz = ZoneInfo(tz_name)
    time_part = (time or "00:00:00").strip()
    if len(time_part) == 5:
        time_part = f"{time_part}:00"
    local = datetime.fromisoformat(f"{date}T{time_part}").replace(tzinfo=local_tz)
    return local.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def normalized_event(
    *,
    source: str,
    country: str,
    name: str,
    event_ts: str,
    impact: str,
    category: str | None = None,
    actual: Any = None,
    estimate: Any = None,
    previous: Any = None,
    unit: str | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    impact_norm = normalize_impact(impact)
    event_id = f"{source}:{event_ts[:10]}:{slug_event_name(name)}"
    return {
        "event_id": event_id,
        "event_ts": event_ts,
        "country": country.upper(),
        "name": name.strip(),
        "impact": impact_norm,
        "category": category,
        "actual": actual,
        "estimate": estimate,
        "previous": previous,
        "unit": unit,
        "source": source,
        "raw": raw or {},
    }
