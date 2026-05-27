from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from alloccontext.rollup.etf import build_etf_context

Scope = Literal["daily", "weekly"]


def _row_to_event(row) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "event_ts": row["event_ts"],
        "country": row["country"],
        "name": row["name"],
        "impact": row["impact"],
        "category": row["category"],
        "actual": row["actual"],
        "estimate": row["estimate"],
        "previous": row["previous"],
        "unit": row["unit"],
        "source": row["source"],
    }


def _value_on_or_before(conn, *, series_id: str, target_date: date) -> tuple[str, float] | None:
    row = conn.execute(
        """
        SELECT obs_date, value
        FROM fred_observations
        WHERE series_id = ? AND obs_date <= ? AND value IS NOT NULL
        ORDER BY obs_date DESC
        LIMIT 1
        """,
        (series_id, target_date.isoformat()),
    ).fetchone()
    if row is None:
        return None
    return str(row["obs_date"]), float(row["value"])


def _latest_value(conn, *, series_id: str) -> tuple[str, float] | None:
    row = conn.execute(
        """
        SELECT obs_date, value
        FROM fred_observations
        WHERE series_id = ? AND value IS NOT NULL
        ORDER BY obs_date DESC
        LIMIT 1
        """,
        (series_id,),
    ).fetchone()
    if row is None:
        return None
    return str(row["obs_date"]), float(row["value"])


def _pct_change(current: float, prior: float) -> float | None:
    if prior == 0:
        return None
    return round((current - prior) / prior * 100.0, 2)


def _build_indicators(conn, config, *, now: datetime) -> dict[str, Any]:
    specs = config.fred.series
    if not specs:
        return {"available": False, "reason": "no_series_configured"}

    as_of_date = now.date()
    indicators: dict[str, Any] = {}
    for spec in specs:
        latest = _latest_value(conn, series_id=spec.id)
        if latest is None:
            continue
        obs_date, value = latest
        entry: dict[str, Any] = {
            "label": spec.label,
            "category": spec.category,
            "value": round(value, 4),
            "obs_date": obs_date,
        }
        for days, key in ((7, "change_7d"), (30, "change_30d")):
            prior = _value_on_or_before(
                conn,
                series_id=spec.id,
                target_date=as_of_date - timedelta(days=days),
            )
            if prior is None:
                continue
            prior_date, prior_value = prior
            delta = round(value - prior_value, 4)
            entry[key] = delta
            entry[f"{key}_from_date"] = prior_date
            pct = _pct_change(value, prior_value)
            if pct is not None:
                entry[key.replace("change", "change_pct")] = pct
        indicators[spec.id] = entry

    if not indicators:
        return {"available": False, "reason": "no_fred_data"}

    return {"available": True, "indicators": indicators}


def _build_events(conn, *, now: datetime, scope: Scope) -> dict[str, Any]:
    past_hours = 24 if scope == "daily" else 24 * 7
    future_days = 7
    past_start = (now - timedelta(hours=past_hours)).isoformat()
    future_end = (now + timedelta(days=future_days)).isoformat()
    now_iso = now.isoformat()

    rows = conn.execute(
        """
        SELECT event_id, event_ts, country, name, impact, category,
               actual, estimate, previous, unit, source
        FROM macro_events
        WHERE event_ts >= ? AND event_ts <= ?
        ORDER BY event_ts ASC
        """,
        (past_start, future_end),
    ).fetchall()

    if not rows:
        return {"available": False, "reason": "no_events"}

    past_key = "past_24h" if scope == "daily" else "past_7d"
    past_events = [_row_to_event(row) for row in rows if row["event_ts"] < now_iso]
    upcoming = [_row_to_event(row) for row in rows if row["event_ts"] >= now_iso]
    sources = sorted({row["source"] for row in rows})

    return {
        "available": True,
        "events": {
            past_key: past_events,
            "next_7d": upcoming,
        },
        "sources": sources,
        "counts": {
            past_key: len(past_events),
            "next_7d": len(upcoming),
        },
    }


def build_macro_context(
    conn,
    config,
    *,
    now: datetime,
    scope: Scope,
) -> dict[str, Any]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    events_block = _build_events(conn, now=now, scope=scope)
    etf_block = build_etf_context(
        conn,
        now=now,
        scope=scope,
        assets=list(config.etf.assets),
    )
    indicators_block = _build_indicators(conn, config, now=now)

    if (
        not events_block.get("available")
        and not etf_block.get("available")
        and not indicators_block.get("available")
    ):
        return {"available": False, "reason": "no_macro_data"}

    sources = sorted(
        set(events_block.get("sources") or [])
        | set(etf_block.get("sources") or [])
        | ({"fred"} if indicators_block.get("available") else set())
    )
    result: dict[str, Any] = {"available": True, "sources": sources}
    if events_block.get("available"):
        result["events"] = events_block["events"]
        result["counts"] = events_block.get("counts", {})
    if etf_block.get("available"):
        result["etf"] = etf_block["assets"]
    if indicators_block.get("available"):
        result["indicators"] = indicators_block["indicators"]
    return result
