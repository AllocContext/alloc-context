from __future__ import annotations

from typing import Any

from alloccontext.rollup.shift_classification import split_notable_shifts


def _kalshi_block(sentiment: dict[str, Any]) -> dict[str, Any]:
    kalshi = sentiment.get("kalshi")
    return kalshi if isinstance(kalshi, dict) else {}


def _fear_greed_block(sentiment: dict[str, Any]) -> dict[str, Any] | None:
    fg = sentiment.get("fear_greed")
    return fg if isinstance(fg, dict) else None


def _allocation_block(portfolio: dict[str, Any]) -> dict[str, Any]:
    """Sleeve drift summary — deprecated on regime; use allocation_analysis."""
    if not portfolio.get("available"):
        return {"available": False}
    analysis = portfolio.get("allocation_analysis")
    if isinstance(analysis, dict) and analysis.get("available"):
        return {
            "available": True,
            "hint": analysis.get("rebalance_hint"),
            "outside_band": analysis.get("outside_band"),
            "max_drift": analysis.get("max_drift"),
            "band": analysis.get("band"),
            "target_allocation_pct": analysis.get("target_allocation_pct"),
        }
    if portfolio.get("rebalance_hint"):
        return {
            "available": True,
            "hint": portfolio.get("rebalance_hint"),
            "outside_band": portfolio.get("outside_band"),
            "max_drift": portfolio.get("max_drift"),
            "band": portfolio.get("band"),
            "target_allocation_pct": portfolio.get("target_allocation_pct"),
        }
    return {"available": False}


def build_regime_context(
    *,
    portfolio: dict[str, Any],
    sentiment: dict[str, Any],
    delta: dict[str, Any],
    market: dict[str, Any] | None = None,
    prior_as_of: str | None,
) -> dict[str, Any]:
    hints: list[dict[str, str]] = []
    allocation = _allocation_block(portfolio)
    volatility: dict[str, Any] = {"available": False}
    sentiment_block: dict[str, Any] = {"available": False}

    kalshi = _kalshi_block(sentiment)
    if kalshi.get("available"):
        vol_regime = kalshi.get("volatility_regime")
        vol_by_asset = kalshi.get("volatility_by_asset")
        if vol_regime or vol_by_asset:
            volatility = {
                "available": True,
                "regime": vol_regime,
                "by_asset": vol_by_asset,
            }
            if vol_regime:
                hints.append(
                    {
                        "kind": "volatility",
                        "code": str(vol_regime),
                        "text": f"Short-horizon volatility regime: {vol_regime}.",
                    }
                )
        tape_summary = kalshi.get("tape_summary")
        leaders_agree = kalshi.get("leaders_agree")
        sentiment_up_frac = kalshi.get("sentiment_up_frac")
        sentiment_block = {
            "available": True,
            "tape_summary": tape_summary,
            "leaders_agree": leaders_agree,
            "sentiment_up_frac": sentiment_up_frac,
        }
        if leaders_agree is False:
            hints.append(
                {
                    "kind": "spot_prediction",
                    "code": "leaders_diverge",
                    "text": "BTC and ETH short-term Kalshi drift disagree.",
                }
            )

    fg = _fear_greed_block(sentiment) if sentiment.get("available") else None
    if fg and fg.get("value") is not None:
        sentiment_block["available"] = True
        sentiment_block["fear_greed_value"] = fg.get("value")
        sentiment_block["fear_greed_classification"] = fg.get("classification")
        classification = fg.get("classification")
        if classification:
            hints.append(
                {
                    "kind": "sentiment",
                    "code": str(classification).lower().replace(" ", "_"),
                    "text": f"Fear & Greed index: {fg['value']} ({classification}).",
                }
            )

    comparison: dict[str, Any] = {
        "prior_as_of": prior_as_of,
        "has_prior_snapshot": bool(prior_as_of),
    }
    if delta.get("available"):
        market_shifts, sleeve_shifts = split_notable_shifts(
            list(delta.get("notable_shifts") or [])
        )
        comparison["market_shifts"] = market_shifts
        comparison["sleeve_shifts"] = sleeve_shifts
        comparison["notable_shifts"] = market_shifts
        for line in market_shifts:
            hints.append({"kind": "delta", "code": "notable_shift", "text": str(line)})

    available = (
        volatility.get("available")
        or sentiment_block.get("available")
        or comparison["has_prior_snapshot"]
    )
    summary_parts = [hint["text"] for hint in hints[:3]]
    summary = " ".join(summary_parts) if summary_parts else None
    risk_off = _build_risk_off(sentiment=sentiment)

    return {
        "available": available,
        "allocation": allocation,
        "volatility": volatility,
        "sentiment": sentiment_block,
        "comparison": comparison,
        "hints": hints,
        "summary": summary,
        "risk_off": risk_off,
    }


def _build_risk_off(*, sentiment: dict[str, Any]) -> dict[str, Any]:
    """Market-wide risk-off score from external sentiment only (ADR-020)."""
    signals: list[str] = []
    score = 0

    fg = _fear_greed_block(sentiment) if sentiment.get("available") else None
    if fg and fg.get("value") is not None:
        value = int(fg["value"])
        if value <= 25:
            score += 35
            signals.append(f"Fear & Greed {value} (extreme fear)")
        elif value <= 40:
            score += 20
            signals.append(f"Fear & Greed {value} (fear)")

    score = min(100, score)
    level = "low"
    if score >= 70:
        level = "high"
    elif score >= 40:
        level = "moderate"

    return {
        "available": bool(signals),
        "score": score,
        "level": level,
        "signals": signals,
    }
