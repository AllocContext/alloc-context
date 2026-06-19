"""Historical regime comparison vs saved context snapshots (ADR-015)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from alloccontext.rollup.comparison import compare_context_bundles
from alloccontext.rollup.snapshots import (
    SnapshotNotFoundError,
    load_context_bundle_snapshot,
    resolve_context_snapshot_as_of,
)

Scope = Literal["daily", "weekly"]

DEFAULT_REGIME_HORIZON_DAYS: tuple[int, ...] = (7, 30)
_RISK_OFF_TRAJECTORY_DELTA = 15

RegimePostureLabel = Literal["RISK_ON", "NEUTRAL", "RISK_OFF", "UNKNOWN"]
RegimeTrajectory = Literal["IMPROVING", "STABLE", "DETERIORATING", "UNKNOWN"]


def _parse_as_of(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fear_greed_value(bundle: dict[str, Any]) -> int | None:
    sentiment = bundle.get("sentiment") if isinstance(bundle.get("sentiment"), dict) else {}
    if not sentiment.get("available"):
        return None
    fg = sentiment.get("fear_greed") if isinstance(sentiment.get("fear_greed"), dict) else {}
    value = fg.get("value")
    return int(value) if value is not None else None


def _btc_change_pct(prior: dict[str, Any], current: dict[str, Any]) -> float | None:
    market_prior = prior.get("market") if isinstance(prior.get("market"), dict) else {}
    market_current = current.get("market") if isinstance(current.get("market"), dict) else {}
    if not market_prior.get("available") or not market_current.get("available"):
        return None
    assets_prior = market_prior.get("assets") if isinstance(market_prior.get("assets"), dict) else {}
    assets_current = market_current.get("assets") if isinstance(market_current.get("assets"), dict) else {}
    prior_btc = assets_prior.get("btc") if isinstance(assets_prior.get("btc"), dict) else {}
    current_btc = assets_current.get("btc") if isinstance(assets_current.get("btc"), dict) else {}
    prior_price = prior_btc.get("price_usd")
    current_price = current_btc.get("price_usd")
    if prior_price is None or current_price is None or float(prior_price) == 0:
        return None
    return round((float(current_price) - float(prior_price)) / float(prior_price) * 100, 2)


def _risk_off_block(bundle: dict[str, Any]) -> dict[str, Any]:
    regime = bundle.get("regime") if isinstance(bundle.get("regime"), dict) else {}
    block = regime.get("risk_off") if isinstance(regime.get("risk_off"), dict) else {}
    return block


def _resolve_baseline_as_of(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    current_as_of: str,
    days: int,
) -> str | None:
    target = _parse_as_of(current_as_of) - timedelta(days=days)
    try:
        return resolve_context_snapshot_as_of(
            conn,
            scope=scope,
            as_of=target.isoformat(),
            mode="at_or_before",
        )
    except SnapshotNotFoundError:
        return None


def _horizon_entry(
    *,
    days: int,
    baseline_as_of: str | None,
    prior: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    if baseline_as_of is None or prior is None:
        return {
            "days": days,
            "available": False,
            "baseline_as_of": None,
            "reason": "no_snapshot_at_or_before_target",
        }

    if baseline_as_of == current.get("as_of"):
        return {
            "days": days,
            "available": False,
            "baseline_as_of": baseline_as_of,
            "reason": "baseline_same_as_current",
        }

    risk_off_then = _risk_off_block(prior)
    risk_off_now = _risk_off_block(current)
    score_then = risk_off_then.get("score")
    score_now = risk_off_now.get("score")
    fg_then = _fear_greed_value(prior)
    fg_now = _fear_greed_value(current)
    diff = compare_context_bundles(prior, current)
    market_shifts = list(diff.get("market_shifts") or [])
    sleeve_shifts = list(diff.get("sleeve_shifts") or [])

    entry: dict[str, Any] = {
        "days": days,
        "available": True,
        "baseline_as_of": baseline_as_of,
        "risk_off": {
            "score_then": score_then,
            "score_now": score_now,
            "level_then": risk_off_then.get("level"),
            "level_now": risk_off_now.get("level"),
        },
        "fear_greed": {
            "then": fg_then,
            "now": fg_now,
            "change": (fg_now - fg_then if fg_then is not None and fg_now is not None else None),
        },
        "btc_change_pct": _btc_change_pct(prior, current),
        "market_shifts": market_shifts,
        "sleeve_shifts": sleeve_shifts,
        "notable_shifts": market_shifts,
    }
    if score_then is not None and score_now is not None:
        entry["risk_off"]["score_delta"] = int(score_now) - int(score_then)
    return entry


def derive_regime_posture(
    current: dict[str, Any],
    *,
    horizon_7d: dict[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic posture label + trajectory from current risk_off and 7d history."""
    risk_off = _risk_off_block(current)
    score = risk_off.get("score")
    level = str(risk_off.get("level") or "").lower()
    fg = _fear_greed_value(current)

    label: RegimePostureLabel = "UNKNOWN"
    if level == "high" or (isinstance(score, int) and score >= 70):
        label = "RISK_OFF"
    elif level == "low" and (not isinstance(score, int) or score < 25):
        label = "RISK_ON" if fg is not None and fg >= 55 else "NEUTRAL"
    elif level in {"moderate", "low"}:
        label = "NEUTRAL"

    trajectory: RegimeTrajectory = "UNKNOWN"
    basis_days: int | None = None
    if horizon_7d and horizon_7d.get("available"):
        basis_days = int(horizon_7d.get("days") or 7)
        score_delta = (horizon_7d.get("risk_off") or {}).get("score_delta")
        if isinstance(score_delta, int):
            if score_delta >= _RISK_OFF_TRAJECTORY_DELTA:
                trajectory = "DETERIORATING"
            elif score_delta <= -_RISK_OFF_TRAJECTORY_DELTA:
                trajectory = "IMPROVING"
            else:
                trajectory = "STABLE"
        else:
            fg_change = (horizon_7d.get("fear_greed") or {}).get("change")
            if isinstance(fg_change, int):
                if fg_change >= 5:
                    trajectory = "IMPROVING"
                elif fg_change <= -5:
                    trajectory = "DETERIORATING"
                else:
                    trajectory = "STABLE"

    return {
        "available": label != "UNKNOWN",
        "label": label,
        "trajectory": trajectory,
        "basis_days": basis_days,
    }


def build_regime_history_comparison(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    current: dict[str, Any],
    horizons: tuple[int, ...] = DEFAULT_REGIME_HORIZON_DAYS,
) -> dict[str, Any]:
    """Compare current bundle to saved snapshots at configured day horizons."""
    current_as_of = str(current.get("as_of") or "")
    if not current_as_of:
        return {"history": [], "posture": {"available": False, "label": "UNKNOWN", "trajectory": "UNKNOWN", "basis_days": None}}

    history: list[dict[str, Any]] = []
    for days in horizons:
        baseline_as_of = _resolve_baseline_as_of(
            conn,
            scope=scope,
            current_as_of=current_as_of,
            days=days,
        )
        prior: dict[str, Any] | None = None
        if baseline_as_of is not None:
            try:
                prior = load_context_bundle_snapshot(conn, scope=scope, as_of=baseline_as_of)
            except SnapshotNotFoundError:
                baseline_as_of = None
        history.append(
            _horizon_entry(
                days=days,
                baseline_as_of=baseline_as_of,
                prior=prior,
                current=current,
            )
        )

    horizon_7d = next((row for row in history if row.get("days") == 7), None)
    posture = derive_regime_posture(current, horizon_7d=horizon_7d)
    return {"history": history, "posture": posture}


def attach_regime_history(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    """Merge historical comparison into ``regime.comparison`` when regime exists."""
    regime = bundle.get("regime")
    if not isinstance(regime, dict):
        return bundle

    comparison = regime.get("comparison")
    if not isinstance(comparison, dict):
        comparison = {}
        regime["comparison"] = comparison

    history_payload = build_regime_history_comparison(conn, scope=scope, current=bundle)
    comparison["history"] = history_payload["history"]
    comparison["posture"] = history_payload["posture"]
    regime["comparison"] = comparison
    bundle["regime"] = regime
    return bundle
