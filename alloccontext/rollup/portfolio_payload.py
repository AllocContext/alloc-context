from __future__ import annotations

from typing import Any

from alloccontext.ingest.kraken_portfolio import PortfolioSnapshot
from alloccontext.ingest.portfolio_holdings import band_allocation_pct
from alloccontext.rollup.allocation_analysis import build_allocation_analysis


def portfolio_dict_from_snapshot(
    snap: PortfolioSnapshot,
    *,
    exchange_id: str | None = None,
    source: str = "live",
) -> dict[str, Any]:
    allocation_pct = band_allocation_pct(snap.holdings)
    payload: dict[str, Any] = {
        "available": True,
        "source": source,
        "as_of": snap.ts,
        "nav_usd": round(float(snap.nav_usd), 2),
        "cash_usd": round(float(snap.cash_usd), 2),
        "holdings": list(snap.holdings),
        "allocation_pct": {k: round(v, 4) for k, v in allocation_pct.items()},
        "prices": dict(snap.prices),
    }
    if exchange_id:
        payload["exchange"] = exchange_id
    if snap.cash_breakdown:
        payload["cash_breakdown"] = dict(snap.cash_breakdown)
    if snap.unrecognized:
        payload["unrecognized"] = list(snap.unrecognized)
    return payload


def attach_allocation_analysis_to_payload(
    payload: dict[str, Any],
    *,
    target_pct: dict[str, float],
    band: float,
) -> dict[str, Any]:
    if not payload.get("available"):
        return payload
    result = dict(payload)
    result["allocation_analysis"] = build_allocation_analysis(
        payload.get("allocation_pct") or {},
        target_pct,
        band,
    )
    return result
