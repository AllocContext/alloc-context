from __future__ import annotations

from typing import Any


def check_allocation_band(
    allocation_pct: dict[str, float],
    target_pct: dict[str, float],
    band: float,
) -> dict[str, Any]:
    """Drift vs target and rebalance hint for symbols in the target map."""
    symbols = sorted(str(key).strip().upper() for key in target_pct if str(key).strip())
    if not symbols:
        return {
            "available": False,
            "reason": "empty_target",
        }

    drift: dict[str, float] = {}
    allocation_out: dict[str, float] = {}
    target_out: dict[str, float] = {}
    for symbol in symbols:
        current = float(allocation_pct.get(symbol) or 0)
        target = float(target_pct.get(symbol) or 0)
        allocation_out[symbol] = round(current, 4)
        target_out[symbol] = round(target, 4)
        drift[symbol] = round(current - target, 4)

    max_drift_symbol = max(drift, key=lambda key: abs(drift[key]))
    max_drift = abs(drift[max_drift_symbol])
    outside_band = max_drift > band
    hint = "within_band" if not outside_band else "consider_rebalance"

    return {
        "available": True,
        "allocation_pct": allocation_out,
        "target_pct": target_out,
        "drift": drift,
        "max_drift": round(max_drift, 4),
        "max_drift_symbol": max_drift_symbol,
        "band": band,
        "outside_band": outside_band,
        "hint": hint,
    }
