from __future__ import annotations

import json
import sqlite3
from typing import Any

from alloccontext.rollup.breadth import build_market_breadth_context


def _allocation_pct(allocation: dict[str, Any], key: str) -> float:
    if key in allocation:
        return float(allocation[key])
    return 0.0


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
    target = dict(config.portfolio.target_allocations)
    btc_pct = _allocation_pct(allocation, "BTC")
    eth_pct = _allocation_pct(allocation, "ETH")
    cash_pct = _allocation_pct(allocation, "CASH")
    drift = {
        "BTC": round(btc_pct - float(target.get("BTC", 0)), 4),
        "ETH": round(eth_pct - float(target.get("ETH", 0)), 4),
        "CASH": round(cash_pct - float(target.get("CASH", 0)), 4),
    }
    max_drift = max(abs(v) for v in drift.values()) if drift else 0.0
    band = float(config.portfolio.rebalance_band)
    if max_drift <= band:
        rebalance_hint = "within_band"
    elif cash_pct > float(target.get("CASH", 0)) + band:
        rebalance_hint = "consider_deploy_cash"
    elif cash_pct < float(target.get("CASH", 0)) - band:
        rebalance_hint = "consider_trim_to_cash"
    else:
        rebalance_hint = "consider_rebalance"

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

    return {
        "available": True,
        "as_of": row["ts"],
        "nav_usd": round(float(row["nav_usd"] or 0), 2),
        "cash_usd": round(float(row["cash_usd"] or 0), 2),
        "allocation_pct": {
            "BTC": round(btc_pct, 4),
            "ETH": round(eth_pct, 4),
            "CASH": round(cash_pct, 4),
        },
        "target_allocation_pct": target,
        "drift": drift,
        "rebalance_hint": rebalance_hint,
        "pnl_usd": {"since_prior_snapshot": pnl_24h},
        "prices": allocation.get("prices") or {},
        "cash_breakdown": allocation.get("cash_breakdown") or {},
    }


def build_market_context(conn: sqlite3.Connection, config) -> dict[str, Any]:
    assets = build_kraken_market_assets(conn, config)
    breadth = build_market_breadth_context(conn)

    if not assets and not breadth.get("available"):
        return {"available": False, "reason": "no_market_data"}

    result: dict[str, Any] = {"available": True, "interval_minutes": config.kraken.ohlc_interval_minutes}
    if assets:
        result["assets"] = assets
    if breadth.get("available"):
        result["breadth"] = breadth
    if not assets:
        result["reason"] = "no_market_bars"
    return result


def build_kraken_market_assets(conn: sqlite3.Connection, config) -> dict[str, Any]:
    from alloccontext.ingest.kraken_client import pair_to_symbol

    assets: dict[str, Any] = {}
    interval = config.kraken.ohlc_interval_minutes
    for pair in config.kraken.pairs:
        symbol = pair_to_symbol(pair)
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
