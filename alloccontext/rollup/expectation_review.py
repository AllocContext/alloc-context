from __future__ import annotations

from typing import Any

from alloccontext.ingest.asset_registry import normalize_canonical_symbol
from alloccontext.rollup.allocation_analysis import weights_from_holdings
from alloccontext.rollup.delta import asset_price_usd, pct_change_since
from alloccontext.rollup.regime_history import derive_regime_posture

_PRICE_MOVE_THRESHOLD_PCT = 2.0
_RELATIVE_MOVE_THRESHOLD_PCT = 2.0
_FEAR_GREED_SENTIMENT_THRESHOLD = 5
_RISK_OFF_SCORE_DELTA = 15
_ALLOCATION_EXCESS_THRESHOLD = 0.005

_VOLATILITY_ORDINAL = {"low": 0, "medium": 1, "high": 2}
_RISK_OFF_ORDINAL = {"low": 0, "moderate": 1, "high": 2}

_VALID_REGIME_POSTURES = frozenset({"RISK_ON", "NEUTRAL", "RISK_OFF"})
_VALID_REGIME_TRAJECTORIES = frozenset({"IMPROVING", "STABLE", "DETERIORATING"})
REGIME_POSTURE_VALUES: tuple[str, ...] = tuple(sorted(_VALID_REGIME_POSTURES))
REGIME_TRAJECTORY_VALUES: tuple[str, ...] = tuple(sorted(_VALID_REGIME_TRAJECTORIES))
_OPPOSITE_REGIME_POSTURES = frozenset({("RISK_ON", "RISK_OFF"), ("RISK_OFF", "RISK_ON")})
_OPPOSITE_REGIME_TRAJECTORIES = frozenset(
    {("IMPROVING", "DETERIORATING"), ("DETERIORATING", "IMPROVING")}
)

V0_CLAIM_TYPES = frozenset(
    {
        "PRICE_STRENGTH",
        "RELATIVE_STRENGTH",
        "MARKET_SENTIMENT",
        "VOLATILITY_REGIME",
        "RISK_APPETITE",
        "REGIME_EXPECTATION",
        "ALLOCATION_FIT",
    }
)


def theses_need_allocation_fit(theses: list[dict[str, Any]]) -> bool:
    for thesis in theses:
        if not isinstance(thesis, dict):
            continue
        for claim in thesis.get("claims") or []:
            if not isinstance(claim, dict):
                continue
            if str(claim.get("type") or "").strip().upper() == "ALLOCATION_FIT":
                return True
    return False


def _portfolio_holds_asset(portfolio: dict[str, Any], symbol: str) -> bool:
    if not portfolio.get("available"):
        return False
    target = normalize_canonical_symbol(symbol)
    for row in portfolio.get("holdings") or []:
        if not isinstance(row, dict):
            continue
        held = normalize_canonical_symbol(str(row.get("symbol") or ""))
        if held == target:
            return True
    return False


def _claim_base(
    *,
    thesis_id: str,
    claim_type: str,
    asset: str | None,
    baseline_as_of: str | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    if baseline_as_of:
        evidence["baseline_as_of"] = baseline_as_of
    return {
        "thesis_id": thesis_id,
        "type": claim_type,
        "asset": asset,
        "status": "unknown",
        "reason": None,
        "evidence": evidence,
    }


def _baseline_as_of(baseline: dict[str, Any] | None) -> str | None:
    if baseline and baseline.get("as_of"):
        return str(baseline["as_of"])
    return None


def _asset_returns(
    baseline: dict[str, Any] | None,
    current: dict[str, Any],
    symbol: str,
) -> tuple[float | None, float | None, float | None, str | None]:
    if baseline is None or not baseline.get("as_of"):
        return None, None, None, "missing_baseline"
    asset = normalize_canonical_symbol(symbol)
    if not _portfolio_holds_asset(current.get("portfolio") or {}, asset):
        return None, None, None, "asset_not_held"
    prior_price = asset_price_usd(baseline, asset)
    current_price = asset_price_usd(current, asset)
    asset_return = pct_change_since(current_price, prior_price)
    if asset_return is None:
        return None, None, None, "missing_quote"
    return asset_return, prior_price, current_price, None


def _score_price_strength(
    *,
    thesis_id: str,
    claim: dict[str, Any],
    baseline: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    asset = normalize_canonical_symbol(str(claim.get("asset") or ""))
    direction = str(claim.get("direction") or "").strip().upper()
    anchor = _baseline_as_of(baseline)
    result = _claim_base(
        thesis_id=thesis_id,
        claim_type="PRICE_STRENGTH",
        asset=asset or None,
        baseline_as_of=anchor,
    )
    if not asset:
        result["reason"] = "missing_quote"
        return result
    asset_return, _, _, reason = _asset_returns(baseline, current, asset)
    if reason:
        result["reason"] = reason
        return result
    assert asset_return is not None
    result["evidence"]["asset_return_pct"] = asset_return
    if direction not in {"UP", "DOWN"}:
        result["reason"] = "invalid_direction"
        return result
    if -_PRICE_MOVE_THRESHOLD_PCT < asset_return < _PRICE_MOVE_THRESHOLD_PCT:
        result["reason"] = "within_noise_band"
        return result
    if direction == "UP":
        result["status"] = (
            "supported" if asset_return >= _PRICE_MOVE_THRESHOLD_PCT else "weakened"
        )
    else:
        result["status"] = (
            "supported" if asset_return <= -_PRICE_MOVE_THRESHOLD_PCT else "weakened"
        )
    return result


def _score_relative_strength(
    *,
    thesis_id: str,
    claim: dict[str, Any],
    baseline: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    asset = normalize_canonical_symbol(str(claim.get("asset") or ""))
    benchmark = normalize_canonical_symbol(str(claim.get("benchmark") or "BTC"))
    anchor = _baseline_as_of(baseline)
    result = _claim_base(
        thesis_id=thesis_id,
        claim_type="RELATIVE_STRENGTH",
        asset=asset or None,
        baseline_as_of=anchor,
    )
    if not asset:
        result["reason"] = "missing_quote"
        return result
    asset_return, _, _, reason = _asset_returns(baseline, current, asset)
    if reason:
        result["reason"] = reason
        return result
    benchmark_return = pct_change_since(
        asset_price_usd(current, benchmark),
        asset_price_usd(baseline, benchmark),
    )
    if benchmark_return is None:
        result["reason"] = "missing_quote"
        return result
    assert asset_return is not None
    relative = round(asset_return - benchmark_return, 2)
    result["evidence"].update(
        {
            "relative_return_pct": relative,
            "asset_return_pct": asset_return,
            "benchmark_return_pct": benchmark_return,
        }
    )
    if relative >= _RELATIVE_MOVE_THRESHOLD_PCT:
        result["status"] = "supported"
    elif relative <= -_RELATIVE_MOVE_THRESHOLD_PCT:
        result["status"] = "weakened"
    else:
        result["reason"] = "within_noise_band"
    return result


def _fear_greed_value(context: dict[str, Any]) -> int | None:
    sentiment = context.get("sentiment") or {}
    if not sentiment.get("available"):
        return None
    fg = sentiment.get("fear_greed") or {}
    value = fg.get("value")
    return int(value) if value is not None else None


def _kalshi_sentiment_up_frac(context: dict[str, Any]) -> float | None:
    sentiment = context.get("sentiment") or {}
    if not sentiment.get("available"):
        return None
    kalshi = sentiment.get("kalshi") or {}
    if not kalshi.get("available"):
        return None
    frac = kalshi.get("sentiment_up_frac")
    return float(frac) if frac is not None else None


def _score_market_sentiment(
    *,
    thesis_id: str,
    claim: dict[str, Any],
    baseline: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    direction = str(claim.get("direction") or "").strip().upper()
    anchor = _baseline_as_of(baseline)
    result = _claim_base(
        thesis_id=thesis_id,
        claim_type="MARKET_SENTIMENT",
        asset=None,
        baseline_as_of=anchor,
    )
    if baseline is None or not baseline.get("as_of"):
        result["reason"] = "missing_baseline"
        return result
    if direction not in {"IMPROVING", "WEAKENING"}:
        result["reason"] = "invalid_direction"
        return result

    prior_fg = _fear_greed_value(baseline)
    current_fg = _fear_greed_value(current)
    fg_change = None
    if prior_fg is not None and current_fg is not None:
        fg_change = current_fg - prior_fg

    prior_frac = _kalshi_sentiment_up_frac(baseline)
    current_frac = _kalshi_sentiment_up_frac(current)
    frac_delta = None
    if prior_frac is not None and current_frac is not None:
        frac_delta = round(current_frac - prior_frac, 4)

    if fg_change is None and frac_delta is None:
        result["reason"] = "sentiment_unavailable"
        return result

    if fg_change is not None:
        result["evidence"]["fear_greed_change"] = fg_change
    if frac_delta is not None:
        result["evidence"]["sentiment_up_frac_delta"] = frac_delta

    # F&G uses ±5; Kalshi up_frac uses any directional move vs baseline.
    improving = False
    weakening = False
    if fg_change is not None:
        if fg_change >= _FEAR_GREED_SENTIMENT_THRESHOLD:
            improving = True
        if fg_change <= -_FEAR_GREED_SENTIMENT_THRESHOLD:
            weakening = True
    if frac_delta is not None:
        if frac_delta > 0:
            improving = True
        if frac_delta < 0:
            weakening = True

    if improving and weakening:
        result["reason"] = "within_noise_band"
        return result
    if direction == "IMPROVING":
        if improving:
            result["status"] = "supported"
        elif weakening:
            result["status"] = "weakened"
        else:
            result["reason"] = "within_noise_band"
    else:
        if weakening:
            result["status"] = "supported"
        elif improving:
            result["status"] = "weakened"
        else:
            result["reason"] = "within_noise_band"
    return result


def _volatility_ordinal(context: dict[str, Any]) -> int | None:
    sentiment = context.get("sentiment") or {}
    if not sentiment.get("available"):
        return None
    kalshi = sentiment.get("kalshi") or {}
    if not kalshi.get("available"):
        return None
    regime = kalshi.get("volatility_regime")
    if regime is None:
        return None
    return _VOLATILITY_ORDINAL.get(str(regime).lower())


def _score_volatility_regime(
    *,
    thesis_id: str,
    claim: dict[str, Any],
    baseline: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    direction = str(claim.get("direction") or "").strip().upper()
    anchor = _baseline_as_of(baseline)
    result = _claim_base(
        thesis_id=thesis_id,
        claim_type="VOLATILITY_REGIME",
        asset=None,
        baseline_as_of=anchor,
    )
    if baseline is None or not baseline.get("as_of"):
        result["reason"] = "missing_baseline"
        return result
    if direction not in {"DECREASING", "INCREASING"}:
        result["reason"] = "invalid_direction"
        return result

    prior_ord = _volatility_ordinal(baseline)
    current_ord = _volatility_ordinal(current)
    if prior_ord is None or current_ord is None:
        result["reason"] = "sentiment_unavailable"
        return result

    labels = ("low", "medium", "high")
    delta = current_ord - prior_ord
    result["evidence"].update(
        {
            "baseline_regime": labels[prior_ord],
            "current_regime": labels[current_ord],
            "ordinal_delta": delta,
        }
    )
    if delta == 0:
        result["reason"] = "within_noise_band"
        return result
    if direction == "DECREASING":
        result["status"] = "supported" if delta < 0 else "weakened"
    else:
        result["status"] = "supported" if delta > 0 else "weakened"
    return result


def _risk_off_block(context: dict[str, Any]) -> dict[str, Any]:
    regime = context.get("regime") or {}
    risk_off = regime.get("risk_off")
    return risk_off if isinstance(risk_off, dict) else {}


def _posture_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    regime = bundle.get("regime") if isinstance(bundle.get("regime"), dict) else {}
    comparison = (
        regime.get("comparison") if isinstance(regime.get("comparison"), dict) else {}
    )
    posture = comparison.get("posture")
    if isinstance(posture, dict):
        return posture
    return derive_regime_posture(bundle, horizon_7d=None)


def _combine_claim_statuses(
    label_status: str,
    label_reason: str | None,
    *,
    trajectory_status: str | None = None,
    trajectory_reason: str | None = None,
) -> tuple[str, str | None]:
    if trajectory_status is None:
        return label_status, label_reason
    if label_status == "weakened" or trajectory_status == "weakened":
        return "weakened", None
    if label_status == "unknown":
        return "unknown", label_reason
    if trajectory_status == "unknown":
        return "unknown", trajectory_reason
    return "supported", None


def _score_posture_label(*, expected: str, actual: str, available: bool) -> tuple[str, str | None]:
    if not available or actual == "UNKNOWN":
        return "unknown", "posture_unavailable"
    if actual == expected:
        return "supported", None
    if (expected, actual) in _OPPOSITE_REGIME_POSTURES:
        return "weakened", None
    return "unknown", "within_noise_band"


def _score_posture_trajectory(*, expected: str, actual: str) -> tuple[str, str | None]:
    if actual == "UNKNOWN":
        return "unknown", "posture_unavailable"
    if actual == expected:
        return "supported", None
    if (expected, actual) in _OPPOSITE_REGIME_TRAJECTORIES:
        return "weakened", None
    return "unknown", "within_noise_band"


def _score_regime_expectation(
    *,
    thesis_id: str,
    claim: dict[str, Any],
    baseline: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    expected_posture = str(claim.get("posture") or "").strip().upper()
    expected_trajectory_raw = claim.get("trajectory")
    expected_trajectory = (
        str(expected_trajectory_raw).strip().upper()
        if expected_trajectory_raw is not None
        else None
    )
    anchor = _baseline_as_of(baseline)
    result = _claim_base(
        thesis_id=thesis_id,
        claim_type="REGIME_EXPECTATION",
        asset=None,
        baseline_as_of=anchor,
    )
    if baseline is None or not baseline.get("as_of"):
        result["reason"] = "missing_baseline"
        return result
    if expected_posture not in _VALID_REGIME_POSTURES:
        result["reason"] = "invalid_posture"
        return result
    if expected_trajectory is not None and expected_trajectory not in _VALID_REGIME_TRAJECTORIES:
        result["reason"] = "invalid_posture"
        return result

    baseline_posture = _posture_from_bundle(baseline)
    current_posture = _posture_from_bundle(current)
    baseline_label = str(baseline_posture.get("label") or "UNKNOWN").upper()
    current_label = str(current_posture.get("label") or "UNKNOWN").upper()
    current_trajectory = str(current_posture.get("trajectory") or "UNKNOWN").upper()
    current_available = bool(current_posture.get("available")) or current_label != "UNKNOWN"

    label_status, label_reason = _score_posture_label(
        expected=expected_posture,
        actual=current_label,
        available=current_available,
    )
    trajectory_status: str | None = None
    trajectory_reason: str | None = None
    if expected_trajectory is not None:
        trajectory_status, trajectory_reason = _score_posture_trajectory(
            expected=expected_trajectory,
            actual=current_trajectory,
        )

    status, reason = _combine_claim_statuses(
        label_status,
        label_reason,
        trajectory_status=trajectory_status,
        trajectory_reason=trajectory_reason,
    )
    result["status"] = status
    result["reason"] = reason
    result["evidence"].update(
        {
            "baseline_posture": baseline_label,
            "current_posture": current_label,
            "current_trajectory": current_trajectory,
        }
    )
    basis_days = current_posture.get("basis_days")
    if basis_days is not None:
        result["evidence"]["basis_days"] = basis_days
    return result


def _score_risk_appetite(
    *,
    thesis_id: str,
    claim: dict[str, Any],
    baseline: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    direction = str(claim.get("direction") or "").strip().upper()
    anchor = _baseline_as_of(baseline)
    result = _claim_base(
        thesis_id=thesis_id,
        claim_type="RISK_APPETITE",
        asset=None,
        baseline_as_of=anchor,
    )
    if baseline is None or not baseline.get("as_of"):
        result["reason"] = "missing_baseline"
        return result
    if direction not in {"INCREASING", "DECREASING"}:
        result["reason"] = "invalid_direction"
        return result

    prior = _risk_off_block(baseline)
    current_block = _risk_off_block(current)
    if not prior.get("available") and not current_block.get("available"):
        result["reason"] = "sentiment_unavailable"
        return result

    prior_level = str(prior.get("level") or "low")
    current_level = str(current_block.get("level") or "low")
    prior_ord = _RISK_OFF_ORDINAL.get(prior_level, 0)
    current_ord = _RISK_OFF_ORDINAL.get(current_level, 0)
    prior_score = int(prior.get("score") or 0)
    current_score = int(current_block.get("score") or 0)
    score_delta = current_score - prior_score
    level_delta = current_ord - prior_ord

    result["evidence"].update(
        {
            "baseline_level": prior_level,
            "current_level": current_level,
            "level_delta": level_delta,
            "score_delta": score_delta,
        }
    )

    increasing = level_delta < 0 or score_delta <= -_RISK_OFF_SCORE_DELTA
    decreasing = level_delta > 0 or score_delta >= _RISK_OFF_SCORE_DELTA
    if increasing and decreasing:
        result["reason"] = "within_noise_band"
        return result
    if not increasing and not decreasing:
        result["reason"] = "within_noise_band"
        return result
    if direction == "INCREASING":
        result["status"] = "supported" if increasing else "weakened"
    else:
        result["status"] = "supported" if decreasing else "weakened"
    return result


def _portfolio_weight_pct(portfolio: dict[str, Any], asset: str) -> float | None:
    weights = weights_from_holdings(portfolio.get("holdings") or [])
    if not weights:
        allocation = portfolio.get("allocation_pct")
        if isinstance(allocation, dict):
            weights = {
                str(key).strip().upper(): float(value)
                for key, value in allocation.items()
                if str(key).strip()
            }
    if asset not in weights:
        return None
    return float(weights[asset])


def _resolve_allocation_fit_target_band(
    claim: dict[str, Any],
    *,
    target_pct: dict[str, float] | None,
    band: float | None,
    asset: str,
) -> tuple[float | None, float | None, str | None]:
    raw_target = claim.get("target_pct")
    if raw_target is not None:
        resolved_target = float(raw_target)
    elif target_pct and asset in target_pct:
        resolved_target = float(target_pct[asset])
    else:
        return None, None, "missing_target"

    raw_band = claim.get("band")
    if raw_band is not None:
        resolved_band = float(raw_band)
    elif band is not None:
        resolved_band = float(band)
    else:
        return None, None, "missing_band"
    return resolved_target, resolved_band, None


def _score_allocation_fit(
    *,
    thesis_id: str,
    claim: dict[str, Any],
    current: dict[str, Any],
    target_pct: dict[str, float] | None,
    band: float | None,
    baseline_as_of: str | None,
) -> dict[str, Any]:
    raw_asset = claim.get("asset")
    asset = normalize_canonical_symbol(str(raw_asset)) if raw_asset else None
    result = _claim_base(
        thesis_id=thesis_id,
        claim_type="ALLOCATION_FIT",
        asset=asset or None,
        baseline_as_of=baseline_as_of,
    )

    if not asset:
        result["reason"] = "asset_required"
        return result

    resolved_target, resolved_band, reason = _resolve_allocation_fit_target_band(
        claim,
        target_pct=target_pct,
        band=band,
        asset=asset,
    )
    if reason:
        result["reason"] = reason
        return result

    portfolio = current.get("portfolio") or {}
    if not portfolio.get("available"):
        result["reason"] = "missing_quote"
        return result

    current_weight = _portfolio_weight_pct(portfolio, asset)
    if current_weight is None:
        result["reason"] = "missing_quote"
        return result

    drift = round(current_weight - resolved_target, 4)
    abs_drift = abs(drift)
    outside_band = abs_drift > resolved_band
    excess = round(abs_drift - resolved_band, 4) if outside_band else 0.0

    result["evidence"].update(
        {
            "weight_pct": current_weight,
            "target_pct": resolved_target,
            "band": resolved_band,
            "drift": drift,
            "outside_band": outside_band,
        }
    )

    if not outside_band:
        result["status"] = "supported"
        return result
    if excess <= _ALLOCATION_EXCESS_THRESHOLD:
        result["reason"] = "within_noise_band"
        return result
    result["status"] = "weakened"
    return result


def _score_claim(
    *,
    thesis_id: str,
    claim: dict[str, Any],
    baseline: dict[str, Any] | None,
    current: dict[str, Any],
    target_pct: dict[str, float] | None,
    band: float | None,
) -> dict[str, Any]:
    claim_type = str(claim.get("type") or "").strip().upper()
    anchor = _baseline_as_of(baseline)
    if claim_type not in V0_CLAIM_TYPES:
        result = _claim_base(
            thesis_id=thesis_id,
            claim_type=claim_type or "UNKNOWN",
            asset=None,
            baseline_as_of=anchor,
        )
        result["reason"] = "unsupported_claim"
        return result

    if claim_type == "PRICE_STRENGTH":
        return _score_price_strength(
            thesis_id=thesis_id, claim=claim, baseline=baseline, current=current
        )
    if claim_type == "RELATIVE_STRENGTH":
        return _score_relative_strength(
            thesis_id=thesis_id, claim=claim, baseline=baseline, current=current
        )
    if claim_type == "MARKET_SENTIMENT":
        return _score_market_sentiment(
            thesis_id=thesis_id, claim=claim, baseline=baseline, current=current
        )
    if claim_type == "VOLATILITY_REGIME":
        return _score_volatility_regime(
            thesis_id=thesis_id, claim=claim, baseline=baseline, current=current
        )
    if claim_type == "RISK_APPETITE":
        return _score_risk_appetite(
            thesis_id=thesis_id, claim=claim, baseline=baseline, current=current
        )
    if claim_type == "REGIME_EXPECTATION":
        return _score_regime_expectation(
            thesis_id=thesis_id, claim=claim, baseline=baseline, current=current
        )
    return _score_allocation_fit(
        thesis_id=thesis_id,
        claim=claim,
        current=current,
        target_pct=target_pct,
        band=band,
        baseline_as_of=anchor,
    )


def build_expectation_review(
    *,
    baseline_bundles: dict[str, dict[str, Any] | None],
    current_bundle: dict[str, Any],
    theses: list[dict[str, Any]],
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
    baseline_resolutions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score local theses against baseline and current ContextBundles."""
    if not theses:
        return {"available": False, "reason": "no_theses_supplied"}

    claims_out: list[dict[str, Any]] = []
    baseline_as_ofs: set[str] = set()
    used_earliest_tolerance = False

    for thesis in theses:
        if not isinstance(thesis, dict):
            continue
        thesis_id = str(thesis.get("id") or "").strip()
        if not thesis_id:
            continue
        recorded_at = str(thesis.get("recorded_at") or "").strip()
        if not recorded_at:
            for claim in thesis.get("claims") or []:
                if not isinstance(claim, dict):
                    continue
                row = _claim_base(
                    thesis_id=thesis_id,
                    claim_type=str(claim.get("type") or "UNKNOWN"),
                    asset=str(claim.get("asset")) if claim.get("asset") else None,
                )
                row["reason"] = "missing_baseline"
                claims_out.append(row)
            continue

        baseline = baseline_bundles.get(thesis_id)
        anchor = _baseline_as_of(baseline)
        if anchor:
            baseline_as_ofs.add(anchor)
        resolution = (baseline_resolutions or {}).get(thesis_id) or {}
        if resolution.get("mode") == "earliest_available":
            used_earliest_tolerance = True

        for claim in thesis.get("claims") or []:
            if not isinstance(claim, dict):
                continue
            row = _score_claim(
                thesis_id=thesis_id,
                claim=claim,
                baseline=baseline,
                current=current_bundle,
                target_pct=target_pct,
                band=band,
            )
            if resolution.get("mode") == "earliest_available":
                requested = resolution.get("requested_as_of")
                if requested and requested != anchor:
                    row["evidence"]["baseline_requested_as_of"] = requested
                    row["evidence"]["baseline_tolerance"] = "earliest_available"
            claims_out.append(row)

    if not claims_out:
        return {"available": False, "reason": "no_valid_claims"}

    supported = sum(1 for row in claims_out if row["status"] == "supported")
    weakened = sum(1 for row in claims_out if row["status"] == "weakened")
    unknown = sum(1 for row in claims_out if row["status"] == "unknown")

    top_baseline_as_of = next(iter(baseline_as_ofs)) if len(baseline_as_ofs) == 1 else None
    result: dict[str, Any] = {
        "available": True,
        "baseline_as_of": top_baseline_as_of,
        "current_as_of": current_bundle.get("as_of"),
        "supported": supported,
        "weakened": weakened,
        "unknown": unknown,
        "claims": claims_out,
    }
    if used_earliest_tolerance:
        result["baseline_tolerance"] = "earliest_available"
    return result


def _claim_identity(row: dict[str, Any]) -> tuple[str, str, str | None]:
    return (
        str(row["thesis_id"]),
        str(row["type"]),
        str(row["asset"]) if row.get("asset") else None,
    )


def collect_replay_checkpoint_as_ofs_from_bundle(
    bundle: dict[str, Any],
    *,
    after_exclusive: str,
    through_inclusive: str,
) -> list[str]:
    """Bridge-sparse checkpoint dates from delta and regime history."""
    candidates: list[str] = []
    delta = bundle.get("delta") or {}
    if isinstance(delta, dict) and delta.get("available") and delta.get("prior_as_of"):
        candidates.append(str(delta["prior_as_of"]))
    regime = bundle.get("regime") or {}
    comparison = (regime.get("comparison") or {}) if isinstance(regime, dict) else {}
    for row in comparison.get("history") or []:
        if isinstance(row, dict) and row.get("baseline_as_of"):
            candidates.append(str(row["baseline_as_of"]))
    if through_inclusive:
        candidates.append(str(through_inclusive))

    filtered: list[str] = []
    seen: set[str] = set()
    for value in sorted(set(candidates)):
        if value <= after_exclusive or value > through_inclusive:
            continue
        if value not in seen:
            filtered.append(value)
            seen.add(value)
    return filtered


def build_expectation_replay(
    *,
    checkpoint_bundles: list[dict[str, Any]],
    baseline_bundles: dict[str, dict[str, Any] | None],
    theses: list[dict[str, Any]],
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
) -> dict[str, Any]:
    """Re-score theses at intervening snapshots (fixed baseline, rolling current)."""
    if not checkpoint_bundles:
        return {"available": False, "reason": "no_checkpoints"}

    checkpoints_out: list[dict[str, Any]] = []
    status_history: dict[tuple[str, str, str | None], list[tuple[str, str]]] = {}

    for checkpoint in checkpoint_bundles:
        as_of = str(checkpoint.get("as_of") or "")
        compact_claims: list[dict[str, Any]] = []
        supported = weakened = unknown = 0

        for thesis in theses:
            if not isinstance(thesis, dict):
                continue
            thesis_id = str(thesis.get("id") or "").strip()
            if not thesis_id:
                continue
            baseline = baseline_bundles.get(thesis_id)
            for claim in thesis.get("claims") or []:
                if not isinstance(claim, dict):
                    continue
                row = _score_claim(
                    thesis_id=thesis_id,
                    claim=claim,
                    baseline=baseline,
                    current=checkpoint,
                    target_pct=target_pct,
                    band=band,
                )
                compact = {
                    "thesis_id": thesis_id,
                    "type": row["type"],
                    "status": row["status"],
                }
                if row.get("asset"):
                    compact["asset"] = row["asset"]
                compact_claims.append(compact)
                key = _claim_identity(row)
                status_history.setdefault(key, []).append((as_of, row["status"]))
                if row["status"] == "supported":
                    supported += 1
                elif row["status"] == "weakened":
                    weakened += 1
                else:
                    unknown += 1

        checkpoints_out.append(
            {
                "as_of": as_of,
                "supported": supported,
                "weakened": weakened,
                "unknown": unknown,
                "claims": compact_claims,
            }
        )

    transitions: list[dict[str, Any]] = []
    for (thesis_id, claim_type, asset), points in status_history.items():
        first_supported: str | None = None
        first_weakened: str | None = None
        for point_as_of, status in points:
            if status == "supported" and first_supported is None:
                first_supported = point_as_of
            if status == "weakened" and first_weakened is None:
                first_weakened = point_as_of
        transition: dict[str, Any] = {
            "thesis_id": thesis_id,
            "type": claim_type,
            "first_supported_as_of": first_supported,
            "first_weakened_as_of": first_weakened,
        }
        if asset:
            transition["asset"] = asset
        transitions.append(transition)

    return {
        "available": True,
        "checkpoint_count": len(checkpoints_out),
        "checkpoints": checkpoints_out,
        "transitions": transitions,
    }
