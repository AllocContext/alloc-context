from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any

from alloccontext.timeutil import utc_now_iso

BRK_DAY1_ORIGIN = date(2009, 1, 1)

BITVIEW_SERIES = (
    "supply_in_profit_share",
    "supply_in_loss_share",
    "supply_in_profit",
    "supply_in_loss",
)


def day1_index_to_date(index: int) -> date:
    return BRK_DAY1_ORIGIN + timedelta(days=int(index))


def _base_url(config) -> str:
    cycle = config.onchain.cycle
    if cycle.provider == "bitview":
        return cycle.bitview_base_url
    if cycle.provider == "brk":
        if not cycle.brk_base_url:
            raise ValueError("onchain.cycle.brk_base_url required when provider=brk")
        return cycle.brk_base_url
    raise ValueError(f"unsupported onchain.cycle.provider: {cycle.provider}")


def check_provider_health(*, base_url: str, timeout: float) -> dict[str, Any]:
    url = f"{base_url}/health"
    request = urllib.request.Request(url, headers={"User-Agent": "alloc-context/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    if isinstance(payload, dict) and payload.get("status") == "healthy":
        return {"ok": True}
    return {"ok": False, "error": "provider_unhealthy"}


def fetch_bitview_bulk(
    *,
    base_url: str,
    start: int,
    timeout: float,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "index": "day",
            "series": ",".join(BITVIEW_SERIES),
            "start": start,
        }
    )
    url = f"{base_url}/api/series/bulk?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "alloc-context/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        from alloccontext.ingest.http_errors import http_error_message

        raise ValueError(http_error_message(exc, context="bitview bulk series")) from exc
    if not isinstance(payload, list):
        raise ValueError("invalid bitview bulk payload")
    if len(payload) != len(BITVIEW_SERIES):
        raise ValueError(
            f"expected {len(BITVIEW_SERIES)} bitview series, got {len(payload)}"
        )
    return payload


def parse_bitview_bulk(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profit_share = payload[0]
    loss_share = payload[1]
    profit_btc = payload[2]
    loss_btc = payload[3]
    start = int(profit_share["start"])
    end = int(profit_share["end"])
    profit_values = list(profit_share.get("data") or [])
    loss_values = list(loss_share.get("data") or [])
    profit_btc_values = list(profit_btc.get("data") or [])
    loss_btc_values = list(loss_btc.get("data") or [])
    lengths = [
        len(profit_values),
        len(loss_values),
        len(profit_btc_values),
        len(loss_btc_values),
    ]
    if not lengths or min(lengths) == 0:
        raise ValueError("empty bitview bulk series")
    length = min(lengths)
    if len(set(lengths)) != 1:
        raise ValueError("bitview bulk series length mismatch")
    expected = end - start + 1
    if length not in {expected, expected - 1}:
        raise ValueError(
            f"bitview bulk row count {length} outside expected range for "
            f"start={start} end={end}"
        )

    rows: list[dict[str, Any]] = []
    for offset in range(length):
        day_index = start + offset
        as_of_date = day1_index_to_date(day_index).isoformat()
        rows.append(
            {
                "as_of_date": as_of_date,
                "supply_profit_pct": float(profit_values[offset]),
                "supply_loss_pct": float(loss_values[offset]),
                "supply_profit_btc": float(profit_btc_values[offset]),
                "supply_loss_btc": float(loss_btc_values[offset]),
                "btc_price_usd": None,
            }
        )
    return rows


def _filter_ingest_rows(rows: list[dict[str, Any]], *, today: date) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for row in rows:
        as_of = date.fromisoformat(str(row["as_of_date"]))
        if as_of <= today:
            kept.append(row)
    return kept


def upsert_onchain_cycle_rows(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    *,
    source: str,
) -> int:
    fetched_at = utc_now_iso()
    count = 0
    for row in rows:
        conn.execute(
            """
            INSERT INTO onchain_cycle_daily(
              as_of_date,
              supply_profit_pct,
              supply_loss_pct,
              supply_profit_btc,
              supply_loss_btc,
              btc_price_usd,
              source,
              ingested_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(as_of_date) DO UPDATE SET
              supply_profit_pct=excluded.supply_profit_pct,
              supply_loss_pct=excluded.supply_loss_pct,
              supply_profit_btc=excluded.supply_profit_btc,
              supply_loss_btc=excluded.supply_loss_btc,
              btc_price_usd=excluded.btc_price_usd,
              source=excluded.source,
              ingested_at=excluded.ingested_at
            """,
            (
                row["as_of_date"],
                row["supply_profit_pct"],
                row["supply_loss_pct"],
                row.get("supply_profit_btc"),
                row.get("supply_loss_btc"),
                row.get("btc_price_usd"),
                source,
                fetched_at,
            ),
        )
        count += 1
    return count


def _table_is_empty(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS count FROM onchain_cycle_daily").fetchone()
    return int(row["count"]) == 0


def refresh_onchain_cycle(conn: sqlite3.Connection, config) -> dict[str, Any]:
    cycle = config.onchain.cycle
    provider = cycle.provider

    try:
        base_url = _base_url(config)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "rows": 0}

    health = check_provider_health(base_url=base_url, timeout=cycle.timeout_seconds)
    if not health.get("ok"):
        return {
            "ok": False,
            "error": health.get("error") or "provider_unavailable",
            "rows": 0,
        }

    if _table_is_empty(conn):
        start = -cycle.backfill_days
    else:
        start = -14

    try:
        payload = fetch_bitview_bulk(
            base_url=base_url,
            start=start,
            timeout=cycle.timeout_seconds,
        )
        rows = parse_bitview_bulk(payload)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        conn.rollback()
        return {"ok": False, "error": str(exc), "rows": 0}

    today = datetime.now(timezone.utc).date()
    rows = _filter_ingest_rows(rows, today=today)
    if not rows:
        return {"ok": False, "error": "empty_response", "rows": 0}

    upserted = upsert_onchain_cycle_rows(conn, rows, source=provider)
    conn.commit()
    return {"ok": True, "rows": upserted, "latest": rows[-1]}
