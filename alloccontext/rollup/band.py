from __future__ import annotations

from typing import Any

_ASSETS = ("BTC", "ETH", "CASH")


def _pct(allocation: dict[str, float], key: str) -> float:
    return float(allocation.get(key) or 0)


def check_allocation_band(
    allocation_pct: dict[str, float],
    target_pct: dict[str, float],
    band: float,
) -> dict[str, Any]:
    """Drift vs target and rebalance hint for BTC/ETH/CASH."""
    btc_pct = _pct(allocation_pct, "BTC")
    eth_pct = _pct(allocation_pct, "ETH")
    cash_pct = _pct(allocation_pct, "CASH")
    drift = {
        "BTC": round(btc_pct - _pct(target_pct, "BTC"), 4),
        "ETH": round(eth_pct - _pct(target_pct, "ETH"), 4),
        "CASH": round(cash_pct - _pct(target_pct, "CASH"), 4),
    }
    max_drift = max(abs(v) for v in drift.values()) if drift else 0.0
    outside_band = max_drift > band
    if not outside_band:
        hint = "within_band"
    elif cash_pct > _pct(target_pct, "CASH") + band:
        hint = "consider_deploy_cash"
    elif cash_pct < _pct(target_pct, "CASH") - band:
        hint = "consider_trim_to_cash"
    else:
        hint = "consider_rebalance"

    return {
        "available": True,
        "allocation_pct": {
            "BTC": round(btc_pct, 4),
            "ETH": round(eth_pct, 4),
            "CASH": round(cash_pct, 4),
        },
        "target_pct": {a: _pct(target_pct, a) for a in _ASSETS},
        "drift": drift,
        "max_drift": round(max_drift, 4),
        "band": band,
        "outside_band": outside_band,
        "hint": hint,
    }
