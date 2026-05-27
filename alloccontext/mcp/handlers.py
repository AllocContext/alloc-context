from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Literal

from alloccontext.rollup.band import check_allocation_band
from alloccontext.rollup.context import Scope
from alloccontext.rollup.macro import build_macro_context
from alloccontext.rollup.portfolio import build_market_context
from alloccontext.rollup.rebalance import compute_rebalance_plan
from alloccontext.rollup.sentiment import build_sentiment_context
from alloccontext.mcp.staleness import with_staleness
from alloccontext.timeutil import utc_now

_ASSETS = ("BTC", "ETH", "CASH")


def _normalize_pct(values: dict[str, float]) -> dict[str, float]:
    return {asset: float(values.get(asset) or 0) for asset in _ASSETS}


Freshness = Literal["cached", "live"]


def validate_freshness(freshness: str) -> Freshness:
    if freshness not in ("cached", "live"):
        raise ValueError("freshness must be 'cached' or 'live'")
    return freshness  # type: ignore[return-value]


def get_market_context(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope = "daily",
    as_of: datetime | None = None,
    freshness: Freshness = "cached",
) -> dict[str, Any]:
    if freshness == "live":
        from alloccontext.ingest.runner import run_ingest

        run_ingest(conn, config)

    now = (as_of or utc_now()).replace(microsecond=0)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    sentiment = build_sentiment_context(conn, config, config.rollup, now=now)
    macro = build_macro_context(conn, config, now=now, scope=scope)
    market = build_market_context(conn, config)

    macro_subset: dict[str, Any]
    if macro.get("available"):
        macro_subset = {
            "available": True,
            "sources": macro.get("sources") or [],
        }
        for key in ("events", "indicators", "counts"):
            if key in macro:
                macro_subset[key] = macro[key]
    else:
        macro_subset = macro

    etf_block: dict[str, Any]
    if macro.get("available") and macro.get("etf"):
        etf_block = {"available": True, "assets": macro["etf"]}
    else:
        etf_block = {"available": False, "reason": "no_etf_data"}

    if market.get("available") and market.get("breadth"):
        breadth = market["breadth"]
    else:
        breadth = {"available": False, "reason": "no_breadth_data"}

    return with_staleness(
        {
            "scope": scope,
            "freshness": freshness,
            "sentiment": sentiment,
            "macro": macro_subset,
            "etf": etf_block,
            "breadth": breadth,
        },
        as_of=now,
    )


def get_rebalance_plan(
    allocation_pct: dict[str, float],
    target_pct: dict[str, float],
    nav_usd: float,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = (as_of or utc_now()).replace(microsecond=0)
    plan = compute_rebalance_plan(
        float(nav_usd),
        _normalize_pct(allocation_pct),
        _normalize_pct(target_pct),
    )
    return with_staleness(
        {
            "allocation_pct": _normalize_pct(allocation_pct),
            "target_pct": _normalize_pct(target_pct),
            **plan,
        },
        as_of=now,
    )


def check_band(
    allocation_pct: dict[str, float],
    target_pct: dict[str, float],
    band: float,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = (as_of or utc_now()).replace(microsecond=0)
    result = check_allocation_band(
        _normalize_pct(allocation_pct),
        _normalize_pct(target_pct),
        float(band),
    )
    return with_staleness(result, as_of=now)


def validate_scope(scope: str) -> Scope:
    if scope not in ("daily", "weekly"):
        raise ValueError("scope must be 'daily' or 'weekly'")
    return scope  # type: ignore[return-value]
