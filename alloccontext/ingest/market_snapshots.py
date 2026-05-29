from __future__ import annotations

import sqlite3
from typing import Any

from alloccontext.timeutil import utc_now_iso


def upsert_crypto_market_snapshot(
    conn: sqlite3.Connection,
    *,
    source: str,
    snapshot_ts: str,
    snapshot: dict[str, Any],
) -> None:
    fetched_at = utc_now_iso()
    conn.execute(
        """
        INSERT INTO crypto_market_snapshots(
          snapshot_ts, source, total_market_cap_usd, btc_dominance_pct,
          eth_dominance_pct, btc_rank, eth_rank, btc_price_usd, eth_price_usd,
          btc_market_cap_usd, eth_market_cap_usd, btc_change_pct_24h,
          eth_change_pct_24h, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, snapshot_ts) DO UPDATE SET
          total_market_cap_usd = excluded.total_market_cap_usd,
          btc_dominance_pct = excluded.btc_dominance_pct,
          eth_dominance_pct = excluded.eth_dominance_pct,
          btc_rank = excluded.btc_rank,
          eth_rank = excluded.eth_rank,
          btc_price_usd = excluded.btc_price_usd,
          eth_price_usd = excluded.eth_price_usd,
          btc_market_cap_usd = excluded.btc_market_cap_usd,
          eth_market_cap_usd = excluded.eth_market_cap_usd,
          btc_change_pct_24h = excluded.btc_change_pct_24h,
          eth_change_pct_24h = excluded.eth_change_pct_24h,
          fetched_at = excluded.fetched_at
        """,
        (
            snapshot_ts,
            source,
            snapshot.get("total_market_cap_usd"),
            snapshot.get("btc_dominance_pct"),
            snapshot.get("eth_dominance_pct"),
            snapshot.get("btc_rank"),
            snapshot.get("eth_rank"),
            snapshot.get("btc_price_usd"),
            snapshot.get("eth_price_usd"),
            snapshot.get("btc_market_cap_usd"),
            snapshot.get("eth_market_cap_usd"),
            snapshot.get("btc_change_pct_24h"),
            snapshot.get("eth_change_pct_24h"),
            fetched_at,
        ),
    )


def latest_snapshot(conn: sqlite3.Connection, source: str):
    return conn.execute(
        """
        SELECT *
        FROM crypto_market_snapshots
        WHERE source = ?
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        (source,),
    ).fetchone()


def prior_snapshot(conn: sqlite3.Connection, source: str, before_ts: str):
    return conn.execute(
        """
        SELECT *
        FROM crypto_market_snapshots
        WHERE source = ? AND snapshot_ts < ?
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        (source, before_ts),
    ).fetchone()


def row_to_dict(row) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "snapshot_ts": row["snapshot_ts"],
        "source": row["source"],
        "total_market_cap_usd": row["total_market_cap_usd"],
        "btc_dominance_pct": row["btc_dominance_pct"],
        "eth_dominance_pct": row["eth_dominance_pct"],
        "btc_rank": row["btc_rank"],
        "eth_rank": row["eth_rank"],
        "btc_price_usd": row["btc_price_usd"],
        "eth_price_usd": row["eth_price_usd"],
        "btc_market_cap_usd": row["btc_market_cap_usd"],
        "eth_market_cap_usd": row["eth_market_cap_usd"],
        "btc_change_pct_24h": row["btc_change_pct_24h"],
        "eth_change_pct_24h": row["eth_change_pct_24h"],
    }


def dominance_delta(current: dict[str, Any], prior: dict[str, Any]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key in ("btc_dominance_pct", "eth_dominance_pct"):
        cur = current.get(key)
        prev = prior.get(key)
        if cur is None or prev is None:
            out[key.replace("_pct", "_change")] = None
        else:
            out[key.replace("_pct", "_change")] = round(float(cur) - float(prev), 4)
    return out
