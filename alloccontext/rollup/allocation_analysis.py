from __future__ import annotations

from typing import Any

from alloccontext.constants import ALLOCATION_ASSETS
from alloccontext.rollup.band import check_allocation_band


def normalize_band_allocation(allocation_pct: dict[str, float]) -> dict[str, float]:
    return {asset: float(allocation_pct.get(asset) or 0) for asset in ALLOCATION_ASSETS}


def build_allocation_analysis(
    allocation_pct: dict[str, float],
    target_pct: dict[str, float],
    band: float,
) -> dict[str, Any]:
    normalized = normalize_band_allocation(allocation_pct)
    band_result = check_allocation_band(normalized, target_pct, float(band))
    return {
        "available": True,
        "allocation_pct": band_result["allocation_pct"],
        "target_allocation_pct": target_pct,
        "drift": band_result["drift"],
        "rebalance_hint": band_result["hint"],
        "outside_band": band_result["outside_band"],
        "max_drift": band_result["max_drift"],
        "band": float(band),
    }
