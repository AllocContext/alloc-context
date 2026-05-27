from __future__ import annotations

import sqlite3
from typing import Any

from alloccontext.horizon import bars_within_horizon, horizon_days
from alloccontext.ingest.exchange.portfolio import writes_portfolio_snapshot
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
    client = build_kraken_client(spot)
    portfolio_skipped = False
    try:
        snap = None
        portfolio_rows = 0
        if writes_portfolio_snapshot(config, "kraken"):
            if creds:
                snap = fetch_portfolio_snapshot(client, spot)
                upsert_portfolio_snapshot(conn, snap)
                portfolio_rows = 1
            else:
                portfolio_skipped = True
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

    result: dict[str, Any] = {
        "ok": True,
        "rows": portfolio_rows + bar_rows,
        "market_bars": bar_rows,
    }
    if snap is not None:
        result["portfolio"] = {
            "ts": snap.ts,
            "nav_usd": snap.nav_usd,
            "cash_usd": snap.cash_usd,
        }
    if portfolio_skipped:
        result["portfolio_skipped"] = True
        result["portfolio_skip_reason"] = "missing_kraken_credentials"
    return result
