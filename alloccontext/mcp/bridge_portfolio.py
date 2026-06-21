from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from alloccontext.config import AppConfig, load_config
from alloccontext.ingest.asset_registry import is_stable, normalize_canonical_symbol
from alloccontext.ingest.exchange.live import (
    LivePortfolioError,
    fetch_live_portfolio_snapshot,
)
from alloccontext.mcp.expectation_review_tool import envelope_expectation_review
from alloccontext.mcp.payer import PayerKeyError, resolve_payer_private_key
from alloccontext.mcp.setup import portfolio_not_configured
from alloccontext.rollup.portfolio_payload import (
    attach_allocation_analysis_to_payload,
    portfolio_dict_from_snapshot,
)
from alloccontext.mcp.validation import validate_band, validate_target_pct, validate_theses
from alloccontext.rollup.expectation_review import (
    build_expectation_replay,
    build_expectation_review,
    collect_replay_checkpoint_as_ofs_from_bundle,
)
from alloccontext.user_config import UserConfig

AssetsScope = Literal["explicit", "portfolio", "default", "portfolio_unavailable"]

UPSTREAM_CONTEXT_ARG_KEYS = frozenset({"scope", "freshness", "assets"})


def bridge_upstream_ready(user: UserConfig) -> bool:
    """True when bridge has a non-empty upstream URL and x402 payer configured."""
    if not user.upstream.strip():
        return False
    try:
        return resolve_payer_private_key(user) is not None
    except PayerKeyError:
        return False


def build_upstream_context_args(
    *,
    scope: str,
    freshness: str,
    assets: list[str] | None,
) -> dict[str, Any]:
    """Privacy-safe args for bridge → hosted market/bundle tools (symbols only)."""
    args = {"scope": scope, "freshness": freshness, "assets": assets}
    if set(args) - UPSTREAM_CONTEXT_ARG_KEYS:
        raise ValueError("upstream context args must be scope, freshness, assets only")
    return args


def attach_assets_scope(payload: dict[str, Any], scope: AssetsScope) -> dict[str, Any]:
    result = dict(payload)
    result["assets_scope"] = scope
    return result


def default_bridge_app_config() -> AppConfig:
    example = (
        Path(__file__).resolve().parent.parent.parent / "config" / "config.example.yaml"
    )
    return load_config(example)


def fetch_user_portfolio(
    user: UserConfig,
    config: AppConfig,
    *,
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
) -> dict[str, Any]:
    creds = user.primary_exchange_credentials()
    if creds is None:
        return portfolio_not_configured()

    try:
        snap = fetch_live_portfolio_snapshot(
            creds.exchange_id,  # type: ignore[arg-type]
            creds.api_key,
            creds.api_secret,
            config,
        )
    except LivePortfolioError as exc:
        return {
            "available": False,
            "reason": "portfolio_fetch_failed",
            "message": str(exc),
        }

    payload = portfolio_dict_from_snapshot(
        snap,
        exchange_id=creds.exchange_id,
        source="live",
    )
    effective_target = target_pct if target_pct is not None else user.target_allocation
    effective_band = band if band is not None else user.band
    if effective_target is not None:
        payload = attach_allocation_analysis_to_payload(
            payload,
            target_pct=effective_target,
            band=effective_band or 0.15,
        )
    return payload


def market_symbols_from_portfolio(portfolio: dict[str, Any]) -> list[str]:
    """Canonical market scope symbols from a portfolio payload (no stables/cash)."""
    if not portfolio.get("available"):
        return []

    symbols: list[str] = []
    seen: set[str] = set()

    for row in portfolio.get("holdings") or []:
        if not isinstance(row, dict):
            continue
        symbol = normalize_canonical_symbol(str(row.get("symbol") or ""))
        if not symbol or symbol in {"USD", "CASH"} or is_stable(symbol):
            continue
        if symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)

    for raw in portfolio.get("unrecognized") or []:
        symbol = normalize_canonical_symbol(str(raw))
        if not symbol or symbol in seen or symbol in {"USD", "CASH"} or is_stable(symbol):
            continue
        symbols.append(symbol)
        seen.add(symbol)

    return symbols


def portfolio_market_symbols(
    user: UserConfig,
    config: AppConfig,
    *,
    portfolio: dict[str, Any] | None = None,
) -> list[str]:
    """Holdings → upstream market `assets` list; empty when portfolio unavailable."""
    payload = portfolio if portfolio is not None else fetch_user_portfolio(user, config)
    return market_symbols_from_portfolio(payload)


def resolve_bridge_assets(
    user: UserConfig,
    config: AppConfig,
    assets: list[str] | None,
    *,
    portfolio: dict[str, Any] | None = None,
) -> tuple[list[str] | None, AssetsScope]:
    """Effective upstream assets and how they were chosen."""
    if assets is not None and len(assets) > 0:
        return assets, "explicit"
    if user.primary_exchange_credentials() is None:
        return assets, "default"
    if portfolio is None:
        return None, "default"
    if not portfolio.get("available"):
        return None, "portfolio_unavailable"
    derived = market_symbols_from_portfolio(portfolio)
    if derived:
        return derived, "portfolio"
    return None, "default"


def merge_assets_omitted(
    payload: dict[str, Any],
    portfolio: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combine upstream `assets_omitted` with local portfolio `unrecognized[]`."""
    omitted: list[str] = [
        normalize_canonical_symbol(str(symbol))
        for symbol in payload.get("assets_omitted") or []
        if str(symbol).strip()
    ]
    seen = set(omitted)

    if portfolio and portfolio.get("available"):
        for raw in portfolio.get("unrecognized") or []:
            symbol = normalize_canonical_symbol(str(raw))
            if symbol and symbol not in seen:
                omitted.append(symbol)
                seen.add(symbol)

    result = dict(payload)
    if omitted:
        result["assets_omitted"] = omitted
    else:
        result.pop("assets_omitted", None)
    return result


def merge_portfolio_into_bundle(
    bundle: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    result = dict(bundle)
    portfolio_body = dict(portfolio)
    analysis = portfolio_body.pop("allocation_analysis", None)
    result["portfolio"] = portfolio_body
    if analysis:
        result["allocation_analysis"] = analysis
    return result


def strip_upstream_allocation_regime(bundle: dict[str, Any]) -> dict[str, Any]:
    """Remove allocation hints from upstream regime when analysis is not local."""
    if bundle.get("allocation_analysis"):
        return bundle
    regime = bundle.get("regime")
    if not isinstance(regime, dict):
        return bundle
    updated = dict(regime)
    updated["allocation"] = {"available": False}
    hints = [
        hint
        for hint in updated.get("hints") or []
        if hint.get("kind") != "allocation"
    ]
    updated["hints"] = hints
    summary_parts = [hint["text"] for hint in hints[:3]]
    updated["summary"] = " ".join(summary_parts) if summary_parts else regime.get("summary")
    result = dict(bundle)
    result["regime"] = updated
    return result


def attach_bridge_expectation_review(
    *,
    user: UserConfig,
    bundle: dict[str, Any],
    scope: str,
    theses: list[dict[str, Any]] | None,
    target_pct: dict[str, float] | None,
    band: float | None,
    fetch_baseline,
    expectation_replay: bool = False,
    fetch_checkpoint=None,
) -> dict[str, Any]:
    """Score local theses on a merged bridge bundle (baselines via upstream)."""
    effective_theses = theses if theses is not None else user.theses
    if not effective_theses:
        return bundle

    validated = validate_theses(effective_theses)
    if not validated:
        return bundle

    by_recorded_at: dict[str, tuple[dict[str, Any] | None, dict[str, Any]]] = {}
    baseline_bundles: dict[str, dict[str, Any] | None] = {}
    baseline_resolutions: dict[str, dict[str, Any]] = {}
    for thesis in validated:
        thesis_id = thesis["id"]
        recorded_at = thesis["recorded_at"]
        if recorded_at not in by_recorded_at:
            baseline = fetch_baseline(scope=scope, recorded_at=recorded_at)
            if isinstance(baseline, dict) and baseline.get("as_of"):
                meta = {
                    "requested_as_of": recorded_at,
                    "resolved_as_of": baseline.get("snapshot_as_of") or baseline.get("as_of"),
                    "mode": baseline.get("baseline_resolution") or "at_or_before",
                }
                by_recorded_at[recorded_at] = (baseline, meta)
            else:
                by_recorded_at[recorded_at] = (
                    None,
                    {
                        "requested_as_of": recorded_at,
                        "resolved_as_of": None,
                        "mode": "missing",
                    },
                )
        bundle_row, meta = by_recorded_at[recorded_at]
        baseline_bundles[thesis_id] = bundle_row
        baseline_resolutions[thesis_id] = meta

    effective_target = target_pct if target_pct is not None else user.target_allocation
    if effective_target is not None:
        effective_target = validate_target_pct(effective_target)
    effective_band = band if band is not None else user.band
    if effective_band is not None:
        effective_band = validate_band(effective_band)

    review = build_expectation_review(
        baseline_bundles=baseline_bundles,
        current_bundle=bundle,
        theses=validated,
        target_pct=effective_target,
        band=effective_band,
        baseline_resolutions=baseline_resolutions,
    )
    if expectation_replay and review.get("available") and fetch_checkpoint is not None:
        baseline_as_ofs = [
            str(meta["resolved_as_of"])
            for meta in baseline_resolutions.values()
            if meta.get("resolved_as_of")
        ]
        after_exclusive = min(baseline_as_ofs) if baseline_as_ofs else ""
        through = str(bundle.get("as_of") or "")
        as_ofs = collect_replay_checkpoint_as_ofs_from_bundle(
            bundle,
            after_exclusive=after_exclusive,
            through_inclusive=through,
        )
        checkpoints: list[dict[str, Any]] = []
        for as_of in as_ofs:
            checkpoint = fetch_checkpoint(scope=scope, as_of=as_of)
            if isinstance(checkpoint, dict) and checkpoint.get("as_of"):
                checkpoints.append(checkpoint)
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
    result = dict(bundle)
    result["expectation_review"] = review
    return result


def build_bridge_expectation_review_payload(
    *,
    user: UserConfig,
    bundle: dict[str, Any],
    scope: str,
    freshness: str,
    theses: list[dict[str, Any]] | None,
    target_pct: dict[str, float] | None,
    band: float | None,
    fetch_baseline,
    expectation_replay: bool = False,
    fetch_checkpoint=None,
) -> dict[str, Any]:
    """Return expectation_review fields for bridge / dedicated MCP tool."""
    merged = attach_bridge_expectation_review(
        user=user,
        bundle=bundle,
        scope=scope,
        theses=theses,
        target_pct=target_pct,
        band=band,
        fetch_baseline=fetch_baseline,
        expectation_replay=expectation_replay,
        fetch_checkpoint=fetch_checkpoint,
    )
    review = merged.get("expectation_review")
    if not isinstance(review, dict):
        return envelope_expectation_review(
            {"available": False, "reason": "no_valid_theses"},
            scope=scope,
            freshness=freshness,
            source=merged,
        )
    payload = dict(review)
    payload["scope"] = scope
    payload["freshness"] = freshness
    if merged.get("as_of"):
        payload["as_of"] = merged["as_of"]
    if merged.get("age_seconds") is not None:
        payload["age_seconds"] = merged["age_seconds"]
    return payload
