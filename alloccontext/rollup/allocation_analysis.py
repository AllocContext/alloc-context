from __future__ import annotations

from typing import Any

from alloccontext.ingest.asset_registry import is_stable
from alloccontext.rollup.band import check_allocation_band


def weights_from_holdings(holdings: list[Any]) -> dict[str, float]:
    """NAV weight fractions keyed by symbol; cash/stables roll into CASH."""
    weights: dict[str, float] = {}
    cash_weight = 0.0
    for row in holdings:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        weight = row.get("weight_pct")
        if not symbol or weight is None:
            continue
        value = float(weight)
        if symbol in {"USD", "CASH"} or is_stable(symbol):
            cash_weight += value
        else:
            weights[symbol] = weights.get(symbol, 0.0) + value
    if cash_weight > 0:
        weights["CASH"] = weights.get("CASH", 0.0) + cash_weight
    return weights


def allocation_weights_from_portfolio(portfolio: dict[str, Any]) -> dict[str, float]:
    weights = weights_from_holdings(portfolio.get("holdings") or [])
    if weights:
        return weights
    allocation = portfolio.get("allocation_pct")
    if isinstance(allocation, dict) and allocation:
        return {
            str(key).strip().upper(): float(value)
            for key, value in allocation.items()
            if str(key).strip()
        }
    return {}


def build_allocation_analysis(
    allocation_pct: dict[str, float],
    target_pct: dict[str, float],
    band: float,
) -> dict[str, Any]:
    band_result = check_allocation_band(allocation_pct, target_pct, float(band))
    if not band_result.get("available"):
        return band_result
    return {
        "available": True,
        "allocation_pct": band_result["allocation_pct"],
        "target_allocation_pct": dict(target_pct),
        "drift": band_result["drift"],
        "rebalance_hint": band_result["hint"],
        "outside_band": band_result["outside_band"],
        "max_drift": band_result["max_drift"],
        "max_drift_symbol": band_result.get("max_drift_symbol"),
        "band": float(band),
    }


def build_allocation_analysis_for_portfolio(
    portfolio: dict[str, Any],
    target_pct: dict[str, float],
    band: float,
) -> dict[str, Any]:
    return build_allocation_analysis(
        allocation_weights_from_portfolio(portfolio),
        target_pct,
        band,
    )
