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
from alloccontext.mcp.assets import (
    apply_assets_filter_to_bundle,
    apply_assets_filter_to_market_payload,
    filter_market_assets,
    validate_view_assets,
)
from alloccontext.mcp.staleness import with_staleness
from alloccontext.rollup.comparison import compare_context_bundles
from alloccontext.rollup.regime import build_regime_context
from alloccontext.rollup.snapshots import (
    SnapshotNotFoundError,
    load_context_bundle_snapshot,
    resolve_context_snapshot_as_of,
)
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


def _apply_allocation_targets(
    portfolio: dict[str, Any],
    config,
    *,
    target_pct: dict[str, float] | None,
    band: float | None,
) -> dict[str, Any]:
    if not portfolio.get("available"):
        return portfolio
    if target_pct is None and band is None:
        return portfolio

    target = _normalize_pct(
        target_pct
        or portfolio.get("target_allocation_pct")
        or dict(config.portfolio.target_allocations)
    )
    band_width = float(
        band if band is not None else portfolio.get("band", config.portfolio.rebalance_band)
    )
    band_result = check_allocation_band(
        portfolio.get("allocation_pct") or {},
        target,
        band_width,
    )
    updated = dict(portfolio)
    updated["target_allocation_pct"] = target
    updated["drift"] = band_result["drift"]
    updated["rebalance_hint"] = band_result["hint"]
    updated["outside_band"] = band_result["outside_band"]
    updated["max_drift"] = band_result["max_drift"]
    updated["band"] = band_width
    return updated


def _attach_regime(bundle: dict[str, Any], config) -> dict[str, Any]:
    bundle["regime"] = build_regime_context(
        portfolio=bundle.get("portfolio") or {},
        sentiment=bundle.get("sentiment") or {},
        delta=bundle.get("delta") or {},
        prior_as_of=bundle.get("prior_as_of"),
        max_cash_risk_off=config.portfolio.max_cash_risk_off,
    )
    return bundle


def get_context_at(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope = "daily",
    as_of: str,
    match: Literal["exact", "at_or_before"] = "at_or_before",
    assets: list[str] | None = None,
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
) -> dict[str, Any]:
    view_assets = validate_view_assets(assets)
    resolved = resolve_context_snapshot_as_of(
        conn,
        scope=scope,
        as_of=as_of,
        mode=match,
    )
    bundle = load_context_bundle_snapshot(conn, scope=scope, as_of=resolved)
    if target_pct is not None or band is not None:
        bundle["portfolio"] = _apply_allocation_targets(
            bundle.get("portfolio") or {},
            config,
            target_pct=target_pct,
            band=band,
        )
    bundle = apply_assets_filter_to_bundle(bundle, view_assets)
    bundle = _attach_regime(bundle, config)
    if target_pct is not None:
        bundle["target_pct"] = _normalize_pct(target_pct)
    if band is not None:
        bundle["band"] = float(band)
    bundle["snapshot_as_of"] = resolved
    bundle["requested_as_of"] = as_of
    bundle["match"] = match
    return bundle


def get_context_delta(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope = "daily",
    prior_as_of: str,
    current_as_of: str | None = None,
    assets: list[str] | None = None,
) -> dict[str, Any]:
    view_assets = validate_view_assets(assets)
    prior_resolved = resolve_context_snapshot_as_of(
        conn,
        scope=scope,
        as_of=prior_as_of,
        mode="at_or_before",
    )
    prior = load_context_bundle_snapshot(conn, scope=scope, as_of=prior_resolved)
    if current_as_of:
        current_resolved = resolve_context_snapshot_as_of(
            conn,
            scope=scope,
            as_of=current_as_of,
            mode="at_or_before",
        )
        current = load_context_bundle_snapshot(conn, scope=scope, as_of=current_resolved)
    else:
        from alloccontext.rollup.context import build_context_bundle

        current = build_context_bundle(
            conn,
            config,
            scope=scope,
            rollup=config.rollup,
            save_snapshot=False,
        )
        current_resolved = current.get("as_of")

    prior = apply_assets_filter_to_bundle(prior, view_assets)
    current = apply_assets_filter_to_bundle(current, view_assets)
    diff = compare_context_bundles(prior, current)
    diff["scope"] = scope
    diff["prior_snapshot_as_of"] = prior_resolved
    diff["current_snapshot_as_of"] = current_resolved
    return diff


def check_allocation_bands(
    allocation_pct: dict[str, float],
    scenarios: list[dict[str, Any]],
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = (as_of or utc_now()).replace(microsecond=0)
    normalized_allocation = _normalize_pct(allocation_pct)
    results: list[dict[str, Any]] = []
    for index, scenario in enumerate(scenarios):
        name = str(scenario.get("name") or f"scenario_{index + 1}")
        target = _normalize_pct(scenario.get("target_pct") or {})
        band = float(scenario.get("band", 0.15))
        check = check_allocation_band(normalized_allocation, target, band)
        results.append(
            {
                "name": name,
                "target_pct": target,
                "band": band,
                **check,
            }
        )
    return with_staleness(
        {
            "allocation_pct": normalized_allocation,
            "scenarios": results,
        },
        as_of=now,
    )


def get_context_bundle(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope = "daily",
    freshness: Freshness = "cached",
    as_of: datetime | None = None,
    assets: list[str] | None = None,
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
) -> dict[str, Any]:
    view_assets = validate_view_assets(assets)
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
    if target_pct is not None or band is not None:
        bundle["portfolio"] = _apply_allocation_targets(
            bundle.get("portfolio") or {},
            config,
            target_pct=target_pct,
            band=band,
        )
    bundle = apply_assets_filter_to_bundle(bundle, view_assets)
    bundle = _attach_regime(bundle, config)
    if target_pct is not None:
        bundle["target_pct"] = _normalize_pct(target_pct)
    if band is not None:
        bundle["band"] = float(band)
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
    assets: list[str] | None = None,
) -> dict[str, Any]:
    view_assets = validate_view_assets(assets)
    ingest_result: dict[str, Any] | None = None
    if freshness == "live":
        from alloccontext.ingest.runner import run_ingest

        ingest_result = run_ingest(conn, config)

    now = (as_of or utc_now()).replace(microsecond=0)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    sentiment = build_sentiment_context(conn, config, config.rollup, now=now)
    macro = build_macro_context(conn, config, now=now, scope=scope)
    market = filter_market_assets(build_market_context(conn, config), view_assets)

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
            "market": market,
            "sentiment": sentiment,
            "macro": macro_subset,
            "etf": etf_block,
            "breadth": breadth,
        },
        as_of=now,
    )
    payload = apply_assets_filter_to_market_payload(payload, view_assets)
    if ingest_result is not None:
        payload["ingest"] = _ingest_summary(ingest_result)
    return payload


def get_rebalance_plan(
    allocation_pct: dict[str, float],
    target_pct: dict[str, float],
    nav_usd: float,
    *,
    exchange: str = "kraken",
    band: float | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    now = (as_of or utc_now()).replace(microsecond=0)
    exchange_id = validate_exchange_id(exchange)
    normalized_allocation = _normalize_pct(allocation_pct)
    normalized_target = _normalize_pct(target_pct)
    plan = compute_rebalance_plan(
        float(nav_usd),
        normalized_allocation,
        normalized_target,
        exchange=exchange_id,
    )
    body: dict[str, Any] = {
        "allocation_pct": normalized_allocation,
        "target_pct": normalized_target,
        **plan,
    }
    if band is not None:
        body["band_check"] = check_allocation_band(
            normalized_allocation,
            normalized_target,
            float(band),
        )
    return with_staleness(body, as_of=now)


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
