from __future__ import annotations

import sqlite3
from typing import Any

from alloccontext.horizon import bars_within_horizon, horizon_days
from alloccontext.ingest.exchange.portfolio import writes_portfolio_snapshot
from alloccontext.ingest.coinbase_client import CoinbaseError
from alloccontext.ingest.coinbase_portfolio import (
    build_coinbase_client,
    fetch_portfolio_snapshot,
    load_coinbase_credentials,
)
from alloccontext.ingest.kraken_portfolio import upsert_market_bars, upsert_portfolio_snapshot


def refresh_coinbase_exchange(conn: sqlite3.Connection, config) -> dict[str, Any]:
    spot = config.exchanges.coinbase
    if not spot.enabled:
        return {"ok": True, "rows": 0, "skipped": True, "reason": "exchange_disabled"}

    if not load_coinbase_credentials():
        return {
            "ok": True,
            "rows": 0,
            "skipped": True,
            "reason": "missing_coinbase_credentials",
        }

    client = build_coinbase_client(spot)
    try:
        snap = None
        portfolio_rows = 0
        if writes_portfolio_snapshot(config, "coinbase"):
            snap = fetch_portfolio_snapshot(client, spot)
            upsert_portfolio_snapshot(conn, snap)
            portfolio_rows = 1
        bar_rows = 0
        for product_id in spot.pairs:
            bars = client.get_ohlc(product_id, spot.ohlc_interval_minutes)
            bars = bars_within_horizon(bars, days=horizon_days(config))
            bar_rows += upsert_market_bars(
                conn,
                pair=product_id,
                interval_minutes=spot.ohlc_interval_minutes,
                bars=bars,
            )
    except CoinbaseError as exc:
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
    return result
