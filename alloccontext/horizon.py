from __future__ import annotations

from datetime import datetime, timedelta, timezone

QUARTERLY_DAYS = 90


def horizon_days(config) -> int:
    return int(getattr(config.horizon, "days", QUARTERLY_DAYS))


def cutoff_unix(*, days: int, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return int((now - timedelta(days=max(1, days))).timestamp())


def cutoff_iso(*, days: int, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    at = (now - timedelta(days=max(1, days))).replace(microsecond=0)
    return at.isoformat()


def bars_within_horizon(
    bars: list[dict[str, float]],
    *,
    days: int,
    now: datetime | None = None,
) -> list[dict[str, float]]:
    floor = cutoff_unix(days=days, now=now)
    return [bar for bar in bars if int(bar["time"]) >= floor]
