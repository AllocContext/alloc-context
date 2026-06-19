from __future__ import annotations

from typing import Any

from alloccontext.ingest.asset_registry import BAND_ASSETS, is_stable, normalize_canonical_symbol

_ALT_REGIME_WEIGHT_THRESHOLD = 0.10
# Regime alt hints require a larger move than delta notable_shifts (2% since prior).
_ALT_REGIME_MOVE_THRESHOLD_PCT = 5.0


def _kalshi_block(sentiment: dict[str, Any]) -> dict[str, Any]:
    kalshi = sentiment.get("kalshi")
    return kalshi if isinstance(kalshi, dict) else {}


def _fear_greed_block(sentiment: dict[str, Any]) -> dict[str, Any] | None:
    fg = sentiment.get("fear_greed")
    return fg if isinstance(fg, dict) else None


def build_regime_context(
    *,
    portfolio: dict[str, Any],
    sentiment: dict[str, Any],
    delta: dict[str, Any],
    market: dict[str, Any] | None = None,
    prior_as_of: str | None,
) -> dict[str, Any]:
    hints: list[dict[str, str]] = []
    allocation: dict[str, Any] = {"available": False}
    volatility: dict[str, Any] = {"available": False}
    sentiment_block: dict[str, Any] = {"available": False}

    if portfolio.get("available"):
        analysis = portfolio.get("allocation_analysis")
        if isinstance(analysis, dict) and analysis.get("available"):
            allocation = {
                "available": True,
                "hint": analysis.get("rebalance_hint"),
                "outside_band": analysis.get("outside_band"),
                "max_drift": analysis.get("max_drift"),
                "band": analysis.get("band"),
                "target_allocation_pct": analysis.get("target_allocation_pct"),
            }
            hint = analysis.get("rebalance_hint")
        elif portfolio.get("rebalance_hint"):
            allocation = {
                "available": True,
                "hint": portfolio.get("rebalance_hint"),
                "outside_band": portfolio.get("outside_band"),
                "max_drift": portfolio.get("max_drift"),
                "band": portfolio.get("band"),
                "target_allocation_pct": portfolio.get("target_allocation_pct"),
            }
            hint = portfolio.get("rebalance_hint")
        else:
            hint = None
        if hint:
            hints.append(
                {
                    "kind": "allocation",
                    "code": str(hint),
                    "text": _allocation_hint_text(str(hint)),
                }
            )

    hints.extend(
        _alt_holding_move_hints(
            portfolio=portfolio,
            market=market or {},
            delta=delta,
        )
    )

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
        comparison["notable_shifts"] = list(delta.get("notable_shifts") or [])
        covered_alts = _holding_move_symbols(hints)
        for line in comparison["notable_shifts"]:
            symbol = _notable_shift_symbol(str(line))
            if symbol and symbol in covered_alts:
                continue
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


def _alt_holding_move_hints(
    *,
    portfolio: dict[str, Any],
    market: dict[str, Any],
    delta: dict[str, Any],
) -> list[dict[str, str]]:
    if not portfolio.get("available"):
        return []

    market_assets = market.get("assets") if market.get("available") else {}
    if not isinstance(market_assets, dict):
        market_assets = {}
    market_changes = delta.get("market") if delta.get("available") else {}
    if not isinstance(market_changes, dict):
        market_changes = {}

    hints: list[dict[str, str]] = []
    for row in portfolio.get("holdings") or []:
        if not isinstance(row, dict):
            continue
        symbol = normalize_canonical_symbol(str(row.get("symbol") or ""))
        if not symbol or symbol in BAND_ASSETS or symbol in {"USD", "CASH"} or is_stable(symbol):
            continue
        weight = row.get("weight_pct")
        if weight is None or float(weight) < _ALT_REGIME_WEIGHT_THRESHOLD:
            continue

        key = symbol.lower()
        block = market_assets.get(key) if isinstance(market_assets.get(key), dict) else {}
        move = (block.get("change_pct") or {}).get("24h") if isinstance(block, dict) else None
        if move is None:
            move = market_changes.get(f"{key}_change_pct_since_prior")

        if move is None or abs(float(move)) < _ALT_REGIME_MOVE_THRESHOLD_PCT:
            continue

        move_f = float(move)
        hints.append(
            {
                "kind": "holding_move",
                "code": f"{key}_large_move",
                "text": (
                    f"{symbol} ({float(weight) * 100:.1f}% weight) moved "
                    f"{move_f:+.1f}% — material for portfolio."
                ),
            }
        )
    return hints


def _holding_move_symbols(hints: list[dict[str, str]]) -> set[str]:
    symbols: set[str] = set()
    for hint in hints:
        if hint.get("kind") != "holding_move":
            continue
        code = str(hint.get("code") or "")
        if code.endswith("_large_move"):
            symbols.add(code[: -len("_large_move")])
    return symbols


def _notable_shift_symbol(line: str) -> str | None:
    token = str(line).strip().split(None, 1)[0] if line else ""
    if not token or token.startswith("$"):
        return None
    symbol = normalize_canonical_symbol(token)
    if not symbol or symbol in BAND_ASSETS:
        return None
    return symbol.lower()


def _allocation_hint_text(code: str) -> str:
    mapping = {
        "within_band": "Portfolio allocation is within the configured drift band.",
        "consider_rebalance": "Allocation drift exceeds the band — consider rebalancing.",
    }
    return mapping.get(code, f"Allocation hint: {code}.")


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
