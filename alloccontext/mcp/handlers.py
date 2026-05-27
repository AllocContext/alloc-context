from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Literal

from alloccontext.rollup.band import check_allocation_band
from alloccontext.ingest.exchange.live import (
    LivePortfolioError,
    fetch_live_portfolio_snapshot,
    portfolio_state_from_snapshot,
    validate_exchange_id,
)
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


def _ingest_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(result.get("ok")),
        "errors": dict(result.get("errors") or {}),
        "counts": dict(result.get("counts") or {}),
    }


def get_context_bundle(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope = "daily",
    freshness: Freshness = "cached",
    as_of: datetime | None = None,
) -> dict[str, Any]:
    ingest_result: dict[str, Any] | None = None
    if freshness == "live":
        from alloccontext.ingest.runner import run_ingest

        ingest_result = run_ingest(conn, config)

    from alloccontext.rollup.context import build_context_bundle

    now = (as_of or utc_now()).replace(microsecond=0)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    bundle = build_context_bundle(
        conn,
        config,
        scope=scope,
        rollup=config.rollup,
        as_of=now,
        save_snapshot=False,
    )
    payload = with_staleness(bundle, as_of=now)
    payload["freshness"] = freshness
    if ingest_result is not None:
        payload["ingest"] = _ingest_summary(ingest_result)
    return payload


def get_market_context(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope = "daily",
    as_of: datetime | None = None,
    freshness: Freshness = "cached",
) -> dict[str, Any]:
    ingest_result: dict[str, Any] | None = None
    if freshness == "live":
        from alloccontext.ingest.runner import run_ingest

        ingest_result = run_ingest(conn, config)

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

    payload = with_staleness(
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
    if ingest_result is not None:
        payload["ingest"] = _ingest_summary(ingest_result)
    return payload


def get_rebalance_plan(
    allocation_pct: dict[str, float],
    target_pct: dict[str, float],
    nav_usd: float,
    *,
    exchange: str = "kraken",
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = (as_of or utc_now()).replace(microsecond=0)
    exchange_id = validate_exchange_id(exchange)
    plan = compute_rebalance_plan(
        float(nav_usd),
        _normalize_pct(allocation_pct),
        _normalize_pct(target_pct),
        exchange=exchange_id,
    )
    return with_staleness(
        {
            "allocation_pct": _normalize_pct(allocation_pct),
            "target_pct": _normalize_pct(target_pct),
            **plan,
        },
        as_of=now,
    )


def get_portfolio_state(
    config,
    *,
    exchange: str,
    api_key: str,
    api_secret: str,
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    exchange_id = validate_exchange_id(exchange)
    target = _normalize_pct(target_pct or dict(config.portfolio.target_allocations))
    band_width = float(
        band if band is not None else config.portfolio.rebalance_band
    )
    try:
        snap = fetch_live_portfolio_snapshot(
            exchange_id,
            api_key,
            api_secret,
            config,
        )
    except LivePortfolioError as exc:
        return with_staleness(
            {
                "available": False,
                "exchange": exchange_id,
                "source": "live",
                "reason": str(exc),
            },
            as_of=as_of or utc_now(),
        )

    payload = portfolio_state_from_snapshot(
        snap,
        exchange_id=exchange_id,
        target_pct=target,
        band=band_width,
    )
    snapshot_ts = payload.pop("snapshot_ts", None)
    as_of_dt = as_of
    if as_of_dt is None and snapshot_ts:
        as_of_dt = datetime.fromisoformat(snapshot_ts)
    return with_staleness(payload, as_of=as_of_dt or utc_now())


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
