from __future__ import annotations

from pathlib import Path
from typing import Any

from alloccontext.config import AppConfig, load_config
from alloccontext.ingest.exchange.live import (
    LivePortfolioError,
    fetch_live_portfolio_snapshot,
)
from alloccontext.mcp.setup import portfolio_not_configured
from alloccontext.rollup.portfolio_payload import (
    attach_allocation_analysis_to_payload,
    portfolio_dict_from_snapshot,
)
from alloccontext.user_config import UserConfig


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
