from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from alloccontext.horizon import cutoff_iso, cutoff_unix, horizon_days


def prune_to_horizon(conn: sqlite3.Connection, config) -> dict[str, int]:
    """Drop rows older than the configured quarterly horizon."""
    days = horizon_days(config)
    fg_cutoff = str(cutoff_unix(days=days))
    bar_cutoff = cutoff_unix(days=days)
    ts_cutoff = cutoff_iso(days=days)

    deleted: dict[str, int] = {}
    deleted["fear_greed"] = conn.execute(
        "DELETE FROM fear_greed WHERE CAST(ts AS INTEGER) < ?",
        (fg_cutoff,),
    ).rowcount
    deleted["market_bars"] = conn.execute(
        "DELETE FROM market_bars WHERE bar_ts < ?",
        (bar_cutoff,),
    ).rowcount
    deleted["portfolio_snapshots"] = conn.execute(
        "DELETE FROM portfolio_snapshots WHERE ts < ?",
        (ts_cutoff,),
    ).rowcount
    deleted["kalshi_snapshots"] = conn.execute(
        "DELETE FROM kalshi_snapshots WHERE ts < ?",
        (ts_cutoff,),
    ).rowcount
    deleted["context_snapshots"] = conn.execute(
        "DELETE FROM context_snapshots WHERE as_of < ?",
        (ts_cutoff,),
    ).rowcount
    deleted["macro_events"] = conn.execute(
        "DELETE FROM macro_events WHERE event_ts < ?",
        (ts_cutoff,),
    ).rowcount
    deleted["etf_flow_days"] = conn.execute(
        "DELETE FROM etf_flow_days WHERE flow_date < ?",
        (ts_cutoff[:10],),
    ).rowcount
    deleted["etf_ticker_flows"] = conn.execute(
        "DELETE FROM etf_ticker_flows WHERE flow_date < ?",
        (ts_cutoff[:10],),
    ).rowcount
    deleted["crypto_market_snapshots"] = conn.execute(
        "DELETE FROM crypto_market_snapshots WHERE snapshot_ts < ?",
        (ts_cutoff,),
    ).rowcount
    deleted["fred_observations"] = conn.execute(
        "DELETE FROM fred_observations WHERE obs_date < ?",
        (ts_cutoff[:10],),
    ).rowcount
    conn.commit()
    return deleted
