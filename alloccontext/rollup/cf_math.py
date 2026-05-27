from __future__ import annotations

import datetime as dt
from typing import Any


def parse_ts(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def pct_change_over_minutes(
    history: dict[str, list[dict[str, Any]]] | None,
    index: str,
    now: dt.datetime,
    *,
    lookback_minutes: float,
    min_samples: int,
) -> float | None:
    rows = history.get(index) if history else None
    if not rows:
        return None
    now = now.astimezone(dt.timezone.utc)
    cutoff = now - dt.timedelta(minutes=lookback_minutes)
    samples: list[tuple[dt.datetime, float]] = []
    for row in rows:
        ts = parse_ts(row.get("at"))
        price = row.get("price")
        if ts is None or price is None or ts < cutoff:
            continue
        samples.append((ts, float(price)))
    if len(samples) < min_samples:
        return None
    samples.sort(key=lambda item: item[0])
    oldest = samples[0][1]
    newest = samples[-1][1]
    if oldest <= 0:
        return None
    return (newest - oldest) / oldest


def range_pct_over_minutes(
    history: dict[str, list[dict[str, Any]]] | None,
    index: str,
    now: dt.datetime,
    *,
    lookback_minutes: float,
    min_samples: int,
) -> float | None:
    rows = history.get(index) if history else None
    if not rows:
        return None
    now = now.astimezone(dt.timezone.utc)
    cutoff = now - dt.timedelta(minutes=lookback_minutes)
    prices: list[float] = []
    for row in rows:
        ts = parse_ts(row.get("at"))
        price = row.get("price")
        if ts is None or price is None or ts < cutoff:
            continue
        prices.append(float(price))
    if len(prices) < min_samples:
        return None
    low = min(prices)
    high = max(prices)
    mid = (low + high) / 2.0
    if mid <= 0:
        return None
    return (high - low) / mid


def trend_pct_for_index(
    history: dict[str, list[dict[str, Any]]] | None,
    index: str,
    now: dt.datetime,
    *,
    lookback_minutes: float,
    min_samples: int,
    enabled: bool = True,
) -> float | None:
    if not enabled:
        return None
    return pct_change_over_minutes(
        history,
        index,
        now,
        lookback_minutes=lookback_minutes,
        min_samples=min_samples,
    )


def scale_pct_map(values: dict[str, float | None]) -> dict[str, float | None]:
    return {
        asset: None if pct is None else round(pct * 100, 4)
        for asset, pct in values.items()
    }
