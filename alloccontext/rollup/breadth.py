from __future__ import annotations

import sqlite3
from typing import Any

from alloccontext.ingest.market_snapshots import (
    dominance_delta,
    latest_snapshot,
    prior_snapshot,
    row_to_dict,
)

_SOURCES = ("coingecko", "coinmarketcap")


def build_market_breadth_context(conn: sqlite3.Connection) -> dict[str, Any]:
    feeds: dict[str, Any] = {}
    for source in _SOURCES:
        row = latest_snapshot(conn, source)
        if row is None:
            feeds[source] = {"available": False, "reason": "no_snapshot"}
            continue
        current = row_to_dict(row)
        prior = row_to_dict(prior_snapshot(conn, source, current["snapshot_ts"]))
        block: dict[str, Any] = {
            "available": True,
            "as_of": current["snapshot_ts"],
            **{k: v for k, v in current.items() if k not in {"snapshot_ts", "source"}},
        }
        if prior:
            block["delta_since_prior"] = dominance_delta(current, prior)
            if prior.get("btc_rank") is not None and current.get("btc_rank") is not None:
                block["delta_since_prior"]["btc_rank_change"] = int(current["btc_rank"]) - int(
                    prior["btc_rank"]
                )
            if prior.get("eth_rank") is not None and current.get("eth_rank") is not None:
                block["delta_since_prior"]["eth_rank_change"] = int(current["eth_rank"]) - int(
                    prior["eth_rank"]
                )
        feeds[source] = block

    if not any(feed.get("available") for feed in feeds.values()):
        return {"available": False, "reason": "no_market_breadth_data"}

    return {"available": True, "feeds": feeds}
