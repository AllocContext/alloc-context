from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Literal

from alloccontext.rollup.allocation_analysis import build_allocation_analysis_for_portfolio
from alloccontext.rollup.band import check_allocation_band
from alloccontext.ingest.exchange.live import (
    LivePortfolioError,
    fetch_live_portfolio_snapshot,
    portfolio_state_from_snapshot,
    validate_cex_exchange_id,
    validate_exchange_id,
)
from alloccontext.rollup.context import Scope
from alloccontext.rollup.macro import build_macro_context
from alloccontext.rollup.portfolio import build_market_context
from alloccontext.rollup.rebalance import collapse_cash_weights, compute_rebalance_plan
from alloccontext.rollup.sentiment import build_sentiment_context
from alloccontext.mcp.assets import (
    apply_assets_filter_to_bundle,
    apply_assets_filter_to_market_payload,
    attach_assets_omitted,
    filter_market_assets,
    resolve_view_assets,
)
from alloccontext.mcp.expectation_review_tool import envelope_expectation_review
from alloccontext.mcp.staleness import with_data_staleness, with_staleness
from alloccontext.mcp.validation import (
    MAX_ALLOCATION_BAND_SCENARIOS,
    McpValidationError,
    validate_band,
    validate_nav_usd,
    validate_target_pct,
    validate_theses,
    normalize_allocation_pct,
)
from alloccontext.rollup.expectation_review import (
    build_expectation_replay,
    build_expectation_review,
    theses_need_allocation_fit,
)
from alloccontext.rollup.comparison import compare_context_bundles
from alloccontext.rollup.regime import build_regime_context
from alloccontext.rollup.regime_history import attach_regime_history
from alloccontext.rollup.snapshots import (
    SnapshotNotFoundError,
    list_context_snapshot_as_ofs_between,
    load_context_bundle_snapshot,
    resolve_context_snapshot_as_of,
    resolve_thesis_baseline_as_of,
)
from alloccontext.constants import ALLOCATION_ASSETS as _ASSETS
from alloccontext.timeutil import utc_now


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


def _run_live_ingest(
    conn: sqlite3.Connection,
    config,
    *,
    freshness: Freshness,
) -> dict[str, Any] | None:
    if freshness != "live":
        return None
    from alloccontext.ingest.runner import run_ingest

    return run_ingest(conn, config)


def _live_ingest_failure_payload(
    ingest_result: dict[str, Any],
    *,
    as_of: datetime,
) -> dict[str, Any] | None:
    """Return a fail-closed MCP payload when live ingest did not succeed.

    Fails closed on required-source failures (``fatal_errors``) and, defensively,
    on any ingest outcome that is not ``ok`` — so a degraded live ingest can
    never be presented as a successful ``freshness=live`` response (ADR-005 C2).
    Optional-only failures keep ``ok=True`` (``ok = not fatal``) and do not trip
    this gate, preserving partial ingest for optional sources.
    """
    fatal = ingest_result.get("fatal_errors") or {}
    ok = bool(ingest_result.get("ok", True))
    if not fatal and ok:
        return None
    return with_staleness(
        {
            "available": False,
            "reason": "live_ingest_failed",
            "fatal_errors": dict(fatal),
            "ingest": _ingest_summary(ingest_result),
            "freshness": "live",
        },
        as_of=as_of,
    )


def _band_allocation_pct(portfolio: dict[str, Any]) -> dict[str, float]:
    allocation = portfolio.get("allocation_pct")
    if isinstance(allocation, dict) and allocation:
        return _normalize_pct(allocation)
    from alloccontext.ingest.portfolio_holdings import band_allocation_pct

    return band_allocation_pct(portfolio.get("holdings") or [])


def _portfolio_allocation_weights(portfolio: dict[str, Any]) -> dict[str, float]:
    from alloccontext.rollup.allocation_analysis import allocation_weights_from_portfolio

    return allocation_weights_from_portfolio(portfolio)


def _load_baseline_bundle(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    recorded_at: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    resolved, mode = resolve_thesis_baseline_as_of(
        conn,
        scope=scope,
        recorded_at=recorded_at,
    )
    meta = {
        "requested_as_of": recorded_at,
        "resolved_as_of": resolved,
        "mode": mode,
    }
    if resolved is None:
        return None, meta
    try:
        bundle = load_context_bundle_snapshot(conn, scope=scope, as_of=resolved)
    except SnapshotNotFoundError:
        meta["resolved_as_of"] = None
        meta["mode"] = "missing"
        return None, meta
    return bundle, meta


def _prepare_baseline_bundle(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope,
    recorded_at: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Load baseline snapshot and rebuild regime for market-wide claim scoring."""
    raw, meta = _load_baseline_bundle(conn, scope=scope, recorded_at=recorded_at)
    if raw is None:
        return None, meta
    return _attach_regime(dict(raw), config, conn=conn, scope=scope), meta


def _baseline_bundles_for_theses(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope,
    theses: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any] | None], dict[str, dict[str, Any]]]:
    by_recorded_at: dict[str, tuple[dict[str, Any] | None, dict[str, Any]]] = {}
    bundles: dict[str, dict[str, Any] | None] = {}
    resolutions: dict[str, dict[str, Any]] = {}
    for thesis in theses:
        thesis_id = thesis["id"]
        recorded_at = thesis.get("recorded_at") or ""
        if recorded_at not in by_recorded_at:
            by_recorded_at[recorded_at] = _prepare_baseline_bundle(
                conn,
                config,
                scope=scope,
                recorded_at=recorded_at,
            )
        bundle, meta = by_recorded_at[recorded_at]
        bundles[thesis_id] = bundle
        resolutions[thesis_id] = meta
    return bundles, resolutions


def _load_replay_checkpoint_bundles(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope,
    after_exclusive: str,
    through_inclusive: str,
) -> list[dict[str, Any]]:
    as_ofs = list_context_snapshot_as_ofs_between(
        conn,
        scope=scope,
        after_exclusive=after_exclusive,
        through_inclusive=through_inclusive,
    )
    if through_inclusive and (
        not as_ofs or as_ofs[-1] != through_inclusive
    ):
        as_ofs.append(through_inclusive)
    bundles: list[dict[str, Any]] = []
    for as_of in as_ofs:
        try:
            raw = load_context_bundle_snapshot(conn, scope=scope, as_of=as_of)
        except SnapshotNotFoundError:
            continue
        bundles.append(_attach_regime(dict(raw), config, conn=conn, scope=scope))
    return bundles


def _effective_allocation_inputs(
    config,
    *,
    target_pct: dict[str, float] | None,
    band: float | None,
) -> tuple[dict[str, float] | None, float | None]:
    effective_target = target_pct
    if effective_target is None and config.portfolio.target_allocations:
        effective_target = validate_target_pct(dict(config.portfolio.target_allocations))
    effective_band = band
    if effective_band is None and config.portfolio.rebalance_band is not None:
        effective_band = validate_band(config.portfolio.rebalance_band)
    return effective_target, effective_band


def _compute_expectation_review(
    conn: sqlite3.Connection,
    config,
    bundle: dict[str, Any],
    *,
    scope: Scope,
    theses: list[dict[str, Any]],
    target_pct: dict[str, float] | None,
    band: float | None,
    expectation_replay: bool = False,
) -> dict[str, Any]:
    validated = validate_theses(theses)
    if not validated:
        return {"available": False, "reason": "no_valid_theses"}

    baseline_bundles, baseline_resolutions = _baseline_bundles_for_theses(
        conn,
        config,
        scope=scope,
        theses=validated,
    )

    effective_target, effective_band = _effective_allocation_inputs(
        config,
        target_pct=target_pct,
        band=band,
    )
    review = build_expectation_review(
        baseline_bundles=baseline_bundles,
        current_bundle=bundle,
        theses=validated,
        target_pct=effective_target,
        band=effective_band,
        baseline_resolutions=baseline_resolutions,
    )
    if expectation_replay and review.get("available"):
        baseline_as_ofs = [
            str(meta["resolved_as_of"])
            for meta in baseline_resolutions.values()
            if meta.get("resolved_as_of")
        ]
        after_exclusive = min(baseline_as_ofs) if baseline_as_ofs else ""
        through = str(bundle.get("as_of") or "")
        checkpoints = _load_replay_checkpoint_bundles(
            conn,
            config,
            scope=scope,
            after_exclusive=after_exclusive,
            through_inclusive=through,
        )
        current_as_of = str(bundle.get("as_of") or "")
        if not checkpoints or str(checkpoints[-1].get("as_of")) != current_as_of:
            checkpoints.append(bundle)
        review["replay"] = build_expectation_replay(
            checkpoint_bundles=checkpoints,
            baseline_bundles=baseline_bundles,
            theses=validated,
            target_pct=effective_target,
            band=effective_band,
        )
    return review


def _attach_expectation_review(
    conn: sqlite3.Connection,
    config,
    bundle: dict[str, Any],
    *,
    scope: Scope,
    theses: list[dict[str, Any]] | None,
    target_pct: dict[str, float] | None,
    band: float | None,
    expectation_replay: bool = False,
) -> dict[str, Any]:
    if not theses:
        return bundle
    review = _compute_expectation_review(
        conn,
        config,
        bundle,
        scope=scope,
        theses=theses,
        target_pct=target_pct,
        band=band,
        expectation_replay=expectation_replay,
    )
    result = dict(bundle)
    result["expectation_review"] = review
    return result


def _attach_allocation_analysis(
    bundle: dict[str, Any],
    config,
    *,
    target_pct: dict[str, float] | None,
    band: float | None,
) -> dict[str, Any]:
    if target_pct is None and band is None:
        return bundle
    portfolio = bundle.get("portfolio") or {}
    if not portfolio.get("available"):
        return bundle

    target = (
        validate_target_pct(target_pct)
        if target_pct is not None
        else validate_target_pct(dict(config.portfolio.target_allocations))
    )
    band_width = (
        validate_band(band)
        if band is not None
        else validate_band(config.portfolio.rebalance_band)
    )
    result = dict(bundle)
    result["allocation_analysis"] = build_allocation_analysis_for_portfolio(
        portfolio,
        target,
        band_width,
    )
    return result


def _alt_quote_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(result.get("ok", True)),
        "rows": int(result.get("rows") or 0),
        "symbols_requested": list(result.get("symbols_requested") or []),
        "symbols_fetched": list(result.get("symbols_fetched") or []),
        "symbols_missing": list(result.get("symbols_missing") or []),
        "skipped": bool(result.get("skipped")),
        "reason": result.get("reason"),
    }


def _live_alt_quote_failure_payload(
    refresh_result: dict[str, Any],
    *,
    as_of: datetime,
) -> dict[str, Any] | None:
    if bool(refresh_result.get("ok", True)):
        return None
    return with_staleness(
        {
            "available": False,
            "reason": "live_alt_quote_refresh_failed",
            "fatal_errors": {},
            "ingest": {
                "ok": False,
                "errors": {},
                "counts": {},
                "alt_quotes": _alt_quote_summary(refresh_result),
            },
            "freshness": "live",
        },
        as_of=as_of,
    )


def _prepare_market_assets(
    conn: sqlite3.Connection,
    config,
    assets: list[str] | None,
    *,
    freshness: Freshness,
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, Any] | None]:
    from alloccontext.ingest.alt_quote_registry import alt_symbols_from_request
    from alloccontext.ingest.alt_quote_store import register_quote_scope
    from alloccontext.ingest.alt_quotes import ensure_alt_quotes, refresh_alt_quotes

    register_quote_scope(conn, assets or [])
    pending = alt_symbols_from_request(assets)
    refresh_result: dict[str, Any] | None = None

    if freshness == "live" and pending:
        refresh_result = refresh_alt_quotes(conn, config, pending)
    elif freshness == "cached" and pending:
        refresh_result = ensure_alt_quotes(conn, config, pending)

    view_assets, assets_omitted = resolve_view_assets(assets, conn=conn)
    return view_assets, assets_omitted, refresh_result


def _attach_alt_quote_ingest(payload: dict[str, Any], refresh_result: dict[str, Any] | None) -> None:
    if refresh_result is None:
        return
    ingest = dict(payload.get("ingest") or {})
    ingest["alt_quotes"] = _alt_quote_summary(refresh_result)
    payload["ingest"] = ingest


def _bundle_reference_dt(bundle: dict[str, Any]) -> datetime | None:
    raw = bundle.get("as_of")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def _attach_regime(
    bundle: dict[str, Any],
    config,
    *,
    conn: sqlite3.Connection | None = None,
    scope: Scope = "daily",
) -> dict[str, Any]:
    portfolio = bundle.get("portfolio") or {}
    analysis = bundle.get("allocation_analysis")
    regime_portfolio = portfolio
    if isinstance(analysis, dict) and analysis.get("available"):
        regime_portfolio = {
            **portfolio,
            "rebalance_hint": analysis.get("rebalance_hint"),
            "outside_band": analysis.get("outside_band"),
            "max_drift": analysis.get("max_drift"),
            "band": analysis.get("band"),
            "target_allocation_pct": analysis.get("target_allocation_pct"),
        }
    bundle["regime"] = build_regime_context(
        portfolio=regime_portfolio,
        sentiment=bundle.get("sentiment") or {},
        delta=bundle.get("delta") or {},
        market=bundle.get("market") or {},
        prior_as_of=bundle.get("prior_as_of"),
        conn=conn,
        config=config,
        now=_bundle_reference_dt(bundle),
    )
    if conn is not None:
        bundle = attach_regime_history(conn, scope=scope, bundle=bundle)
    return bundle


def get_context_at(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope = "daily",
    as_of: str,
    match: Literal["exact", "at_or_before", "thesis_baseline"] = "at_or_before",
    assets: list[str] | None = None,
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
) -> dict[str, Any]:
    view_assets, assets_omitted = resolve_view_assets(assets, conn=conn)
    baseline_mode: str | None = None
    try:
        if match == "thesis_baseline":
            resolved, baseline_mode = resolve_thesis_baseline_as_of(
                conn,
                scope=scope,
                recorded_at=as_of,
            )
            if resolved is None:
                raise SnapshotNotFoundError(f"no {scope} snapshot for thesis baseline")
        else:
            resolved = resolve_context_snapshot_as_of(
                conn,
                scope=scope,
                as_of=as_of,
                mode=match,
            )
        bundle = load_context_bundle_snapshot(conn, scope=scope, as_of=resolved)
    except SnapshotNotFoundError as exc:
        return {
            "available": False,
            "reason": str(exc),
            "scope": scope,
            "requested_as_of": as_of,
            "match": match,
        }
    if target_pct is not None or band is not None:
        bundle = _attach_allocation_analysis(
            bundle,
            config,
            target_pct=target_pct,
            band=band,
        )
    bundle = apply_assets_filter_to_bundle(bundle, view_assets)
    bundle = _attach_regime(bundle, config, conn=conn, scope=scope)
    if target_pct is not None:
        bundle["target_pct"] = validate_target_pct(target_pct)
    if band is not None:
        bundle["band"] = validate_band(band)
    bundle["snapshot_as_of"] = resolved
    bundle["requested_as_of"] = as_of
    bundle["match"] = match
    if baseline_mode is not None:
        bundle["baseline_resolution"] = baseline_mode
    return attach_assets_omitted(bundle, assets_omitted)


def get_context_delta(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope = "daily",
    prior_as_of: str,
    current_as_of: str | None = None,
    assets: list[str] | None = None,
) -> dict[str, Any]:
    view_assets, assets_omitted = resolve_view_assets(assets, conn=conn)
    try:
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
    except SnapshotNotFoundError as exc:
        return {
            "available": False,
            "reason": str(exc),
            "scope": scope,
            "prior_as_of": prior_as_of,
            "current_as_of": current_as_of,
        }

    prior = apply_assets_filter_to_bundle(prior, view_assets)
    current = apply_assets_filter_to_bundle(current, view_assets)
    diff = compare_context_bundles(prior, current)
    diff["scope"] = scope
    diff["prior_snapshot_as_of"] = prior_resolved
    diff["current_snapshot_as_of"] = current_resolved
    return attach_assets_omitted(diff, assets_omitted)


def check_allocation_bands(
    allocation_pct: dict[str, float],
    scenarios: list[dict[str, Any]],
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(scenarios, list):
        raise McpValidationError("scenarios must be a list")
    if len(scenarios) > MAX_ALLOCATION_BAND_SCENARIOS:
        raise McpValidationError(
            f"scenarios exceeds maximum of {MAX_ALLOCATION_BAND_SCENARIOS}"
        )
    now = (as_of or utc_now()).replace(microsecond=0)
    normalized_allocation = normalize_allocation_pct(allocation_pct)
    results: list[dict[str, Any]] = []
    for index, scenario in enumerate(scenarios):
        name = str(scenario.get("name") or f"scenario_{index + 1}")
        target = validate_target_pct(scenario.get("target_pct") or {})
        band = validate_band(scenario.get("band", 0.15))
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
    theses: list[dict[str, Any]] | None = None,
    expectation_replay: bool = False,
) -> dict[str, Any]:
    now = (as_of or utc_now()).replace(microsecond=0)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    ingest_result = _run_live_ingest(conn, config, freshness=freshness)
    if ingest_result is not None:
        failure = _live_ingest_failure_payload(ingest_result, as_of=now)
        if failure is not None:
            return failure

    view_assets, assets_omitted, refresh_result = _prepare_market_assets(
        conn,
        config,
        assets,
        freshness=freshness,
    )

    if refresh_result is not None and freshness == "live":
        failure = _live_alt_quote_failure_payload(refresh_result, as_of=now)
        if failure is not None:
            return failure

    from alloccontext.rollup.context import build_context_bundle

    alt_symbols = tuple(
        asset for asset in view_assets if asset not in {"BTC", "ETH", "CASH"}
    )
    bundle = build_context_bundle(
        conn,
        config,
        scope=scope,
        rollup=config.rollup,
        as_of=now,
        save_snapshot=False,
        alt_symbols=alt_symbols,
    )
    validated_theses = validate_theses(theses) if theses else []
    need_allocation = theses_need_allocation_fit(validated_theses)
    effective_target, effective_band = _effective_allocation_inputs(
        config,
        target_pct=target_pct,
        band=band,
    )
    if target_pct is not None or band is not None:
        bundle = _attach_allocation_analysis(
            bundle,
            config,
            target_pct=target_pct,
            band=band,
        )
    elif need_allocation and effective_target is not None:
        bundle = _attach_allocation_analysis(
            bundle,
            config,
            target_pct=effective_target,
            band=effective_band,
        )
    bundle = apply_assets_filter_to_bundle(bundle, view_assets)
    bundle = _attach_regime(bundle, config, conn=conn, scope=scope)
    bundle = _attach_expectation_review(
        conn,
        config,
        bundle,
        scope=scope,
        theses=theses,
        target_pct=target_pct,
        band=band,
        expectation_replay=expectation_replay,
    )
    if target_pct is not None:
        bundle["target_pct"] = validate_target_pct(target_pct)
    if band is not None:
        bundle["band"] = validate_band(band)
    payload = with_staleness(bundle, as_of=now)
    payload["freshness"] = freshness
    with_data_staleness(payload, now=now)
    if ingest_result is not None:
        payload["ingest"] = _ingest_summary(ingest_result)
    _attach_alt_quote_ingest(payload, refresh_result)
    return attach_assets_omitted(payload, assets_omitted)


def get_expectation_review(
    conn: sqlite3.Connection,
    config,
    *,
    scope: Scope = "daily",
    freshness: Freshness = "cached",
    theses: list[dict[str, Any]] | None = None,
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
    expectation_replay: bool = False,
) -> dict[str, Any]:
    """Score local theses without returning the full ContextBundle."""
    if not theses:
        now = utc_now().replace(microsecond=0)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return with_staleness(
            {
                "available": False,
                "reason": "no_theses_supplied",
                "scope": scope,
                "freshness": freshness,
            },
            as_of=now,
        )

    bundle = get_context_bundle(
        conn,
        config,
        scope=scope,
        freshness=freshness,
        target_pct=target_pct,
        band=band,
        theses=theses,
        expectation_replay=expectation_replay,
    )
    if bundle.get("available") is False:
        return envelope_expectation_review(
            bundle,
            scope=scope,
            freshness=freshness,
            source=bundle,
        )

    review = bundle.get("expectation_review")
    if not isinstance(review, dict):
        review = {"available": False, "reason": "no_valid_theses"}

    payload = dict(review)
    payload["scope"] = scope
    payload["freshness"] = freshness
    if bundle.get("as_of"):
        payload["as_of"] = bundle["as_of"]
    if bundle.get("age_seconds") is not None:
        payload["age_seconds"] = bundle["age_seconds"]
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
    now = (as_of or utc_now()).replace(microsecond=0)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    ingest_result = _run_live_ingest(conn, config, freshness=freshness)
    if ingest_result is not None:
        failure = _live_ingest_failure_payload(ingest_result, as_of=now)
        if failure is not None:
            return failure

    view_assets, assets_omitted, refresh_result = _prepare_market_assets(
        conn,
        config,
        assets,
        freshness=freshness,
    )

    if refresh_result is not None and freshness == "live":
        failure = _live_alt_quote_failure_payload(refresh_result, as_of=now)
        if failure is not None:
            return failure

    sentiment = build_sentiment_context(conn, config, config.rollup, now=now)
    macro = build_macro_context(conn, config, now=now, scope=scope)
    alt_symbols = tuple(
        asset for asset in view_assets if asset not in {"BTC", "ETH", "CASH"}
    )
    market = filter_market_assets(
        build_market_context(conn, config, alt_symbols=alt_symbols),
        view_assets,
    )

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
    with_data_staleness(payload, now=now)
    if ingest_result is not None:
        payload["ingest"] = _ingest_summary(ingest_result)
    _attach_alt_quote_ingest(payload, refresh_result)
    return attach_assets_omitted(payload, assets_omitted)


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
    exchange_id = validate_cex_exchange_id(exchange)
    normalized_allocation = normalize_allocation_pct(allocation_pct)
    normalized_target = validate_target_pct(target_pct)
    collapsed_allocation = collapse_cash_weights(normalized_allocation)
    collapsed_target = collapse_cash_weights(normalized_target)
    nav = validate_nav_usd(nav_usd)
    plan = compute_rebalance_plan(
        nav,
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
            collapsed_allocation,
            collapsed_target,
            validate_band(band),
        )
    return with_staleness(body, as_of=now)


def get_portfolio_state(
    config,
    *,
    exchange: str,
    api_key: str = "",
    api_secret: str = "",
    wallet_address: str | None = None,
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    exchange_id = validate_exchange_id(exchange)
    try:
        snap = fetch_live_portfolio_snapshot(
            exchange_id,
            api_key,
            api_secret,
            config,
            wallet_address=wallet_address,
        )
    except LivePortfolioError as exc:
        unavailable: dict[str, Any] = {
            "available": False,
            "exchange": exchange_id,
            "source": "live",
            "reason": str(exc),
        }
        if exchange_id == "wallet" and wallet_address:
            unavailable["wallet_address"] = wallet_address.strip()
        return with_staleness(unavailable, as_of=as_of or utc_now())

    payload = portfolio_state_from_snapshot(
        snap,
        exchange_id=exchange_id,
        target_pct=target_pct,
        band=band,
    )
    if exchange_id == "wallet" and wallet_address:
        payload["wallet_address"] = wallet_address.strip()
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
        normalize_allocation_pct(allocation_pct),
        validate_target_pct(target_pct),
        validate_band(band),
    )
    return with_staleness(result, as_of=now)


def validate_scope(scope: str) -> Scope:
    if scope not in ("daily", "weekly"):
        raise ValueError("scope must be 'daily' or 'weekly'")
    return scope  # type: ignore[return-value]
