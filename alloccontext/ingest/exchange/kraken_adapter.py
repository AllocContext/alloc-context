from __future__ import annotations

import sqlite3
from typing import Any

from alloccontext.horizon import bars_within_horizon, horizon_days
from alloccontext.ingest.kraken_client import KrakenError
from alloccontext.ingest.kraken_portfolio import (
    build_kraken_client,
    fetch_portfolio_snapshot,
    load_kraken_credentials,
    upsert_market_bars,
    upsert_portfolio_snapshot,
)


def refresh_kraken_exchange(conn: sqlite3.Connection, config) -> dict[str, Any]:
    spot = config.exchanges.kraken
    if not spot.enabled:
        return {"ok": True, "rows": 0, "skipped": True, "reason": "exchange_disabled"}

    creds = load_kraken_credentials()
    if not creds:
        return {
            "ok": True,
            "rows": 0,
            "skipped": True,
            "reason": "missing_kraken_credentials",
        }

    client = build_kraken_client(spot)
    try:
        snap = fetch_portfolio_snapshot(client, spot)
        upsert_portfolio_snapshot(conn, snap)
        bar_rows = 0
        for pair in spot.pairs:
            bars = client.get_ohlc(pair, spot.ohlc_interval_minutes)
            bars = bars_within_horizon(bars, days=horizon_days(config))
            bar_rows += upsert_market_bars(
                conn,
                pair=pair,
                interval_minutes=spot.ohlc_interval_minutes,
                bars=bars,
            )
    except KrakenError as exc:
        return {"ok": False, "error": str(exc), "rows": 0}

    return {
        "ok": True,
        "rows": 1 + bar_rows,
        "portfolio": {
            "ts": snap.ts,
            "nav_usd": snap.nav_usd,
            "cash_usd": snap.cash_usd,
        },
        "market_bars": bar_rows,
    }
