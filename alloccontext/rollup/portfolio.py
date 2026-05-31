from __future__ import annotations

import json
import sqlite3
from typing import Any

from alloccontext.ingest.portfolio_holdings import (
    band_allocation_pct,
    legacy_holdings_from_allocation,
)
from alloccontext.ingest.alt_quote_store import latest_alt_quotes
from alloccontext.ingest.asset_registry import BAND_ASSETS
from alloccontext.rollup.breadth import build_market_breadth_context


def build_portfolio_context(conn: sqlite3.Connection, config) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT ts, nav_usd, cash_usd, allocation_json
        FROM portfolio_snapshots ORDER BY ts DESC LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {"available": False, "reason": "no_portfolio_snapshot"}

    allocation = json.loads(row["allocation_json"] or "{}")
    nav_usd = round(float(row["nav_usd"] or 0), 2)
    cash_usd = round(float(row["cash_usd"] or 0), 2)
    holdings = legacy_holdings_from_allocation(
        allocation,
        nav_usd=nav_usd,
        cash_usd=cash_usd,
    )
    allocation_pct = band_allocation_pct(holdings)

    prior = conn.execute(
        """
        SELECT nav_usd FROM portfolio_snapshots
        WHERE ts < ?
        ORDER BY ts DESC LIMIT 1
        """,
        (row["ts"],),
    ).fetchone()

    pnl_24h = None
    if prior and prior["nav_usd"] is not None and row["nav_usd"] is not None:
        pnl_24h = round(float(row["nav_usd"]) - float(prior["nav_usd"]), 2)

    payload: dict[str, Any] = {
        "available": True,
        "as_of": row["ts"],
        "nav_usd": nav_usd,
        "cash_usd": cash_usd,
        "holdings": holdings,
        "allocation_pct": {key: round(value, 4) for key, value in allocation_pct.items()},
        "pnl_usd": {"since_prior_snapshot": pnl_24h},
        "prices": allocation.get("prices") or {},
        "cash_breakdown": allocation.get("cash_breakdown") or {},
    }
    unrecognized = allocation.get("unrecognized")
    if unrecognized:
        payload["unrecognized"] = list(unrecognized)
    return payload


def build_market_context(
    conn: sqlite3.Connection,
    config,
    *,
    alt_symbols: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    spot = config.exchanges.primary_spot()
    assets = build_spot_market_assets(conn, spot)
    if alt_symbols:
        assets.update(build_alt_market_assets(conn, alt_symbols))
    breadth = build_market_breadth_context(conn)

    if not assets and not breadth.get("available"):
        return {"available": False, "reason": "no_market_data"}

    result: dict[str, Any] = {"available": True, "interval_minutes": spot.ohlc_interval_minutes}
    if assets:
        result["assets"] = assets
    if breadth.get("available"):
        result["breadth"] = breadth
    if not assets:
        result["reason"] = "no_market_bars"
    return result


def _spot_pair_to_symbol(pair: str) -> str:
    if "-" in pair:
        from alloccontext.ingest.coinbase_client import product_to_symbol

        return product_to_symbol(pair)
    from alloccontext.ingest.kraken_client import pair_to_symbol

    return pair_to_symbol(pair)


def build_spot_market_assets(conn: sqlite3.Connection, spot) -> dict[str, Any]:
    assets: dict[str, Any] = {}
    interval = spot.ohlc_interval_minutes
    for pair in spot.pairs:
        symbol = _spot_pair_to_symbol(pair)
        rows = conn.execute(
            """
            SELECT bar_ts, close FROM market_bars
            WHERE pair = ? AND interval_minutes = ?
            ORDER BY bar_ts DESC LIMIT 2
            """,
            (pair, interval),
        ).fetchall()
        if not rows:
            continue
        latest = float(rows[0]["close"])
        change_pct = None
        if len(rows) >= 2 and float(rows[1]["close"]) > 0:
            prior = float(rows[1]["close"])
            change_pct = round((latest - prior) / prior * 100, 2)
        assets[symbol.lower()] = {
            "pair": pair,
            "price_usd": round(latest, 2),
            "change_pct": {"1_bar": change_pct},
        }
    return assets


def build_alt_market_assets(
    conn: sqlite3.Connection,
    alt_symbols: tuple[str, ...],
) -> dict[str, Any]:
    wanted = [
        symbol.upper()
        for symbol in alt_symbols
        if symbol.upper() not in BAND_ASSETS
    ]
    if not wanted:
        return {}

    assets: dict[str, Any] = {}
    for symbol, quote in latest_alt_quotes(conn, wanted).items():
        block: dict[str, Any] = {
            "pair": f"{symbol}-USD",
            "price_usd": round(float(quote.price_usd), 2),
            "source": quote.source,
        }
        if quote.change_pct_24h is not None:
            block["change_pct"] = {"24h": round(float(quote.change_pct_24h), 2)}
        assets[symbol.lower()] = block
    return assets
