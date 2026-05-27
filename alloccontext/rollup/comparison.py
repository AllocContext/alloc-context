from __future__ import annotations

from typing import Any


def _allocation_drift_lines(
    prior: dict[str, Any],
    current: dict[str, Any],
) -> list[str]:
    lines: list[str] = []
    prior_alloc = (prior.get("portfolio") or {}).get("allocation_pct") or {}
    current_alloc = (current.get("portfolio") or {}).get("allocation_pct") or {}
    for asset in ("BTC", "ETH", "CASH"):
        before = prior_alloc.get(asset)
        after = current_alloc.get(asset)
        if before is None or after is None:
            continue
        delta_pp = round((float(after) - float(before)) * 100, 1)
        if abs(delta_pp) >= 1.0:
            lines.append(f"{asset} allocation {delta_pp:+.1f} pp")
    return lines


def compare_context_bundles(
    prior: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    """Structured diff between two archived or live ContextBundles."""
    prior_as_of = prior.get("as_of")
    current_as_of = current.get("as_of")
    notable: list[str] = []

    prior_delta = prior.get("delta") or {}
    current_delta = current.get("delta") or {}
    for block in (prior_delta, current_delta):
        for line in block.get("notable_shifts") or []:
            if line not in notable:
                notable.append(str(line))

    notable.extend(_allocation_drift_lines(prior, current))

    prior_fg = ((prior.get("sentiment") or {}).get("fear_greed") or {}).get("value")
    current_fg = ((current.get("sentiment") or {}).get("fear_greed") or {}).get("value")
    if prior_fg is not None and current_fg is not None:
        change = int(current_fg) - int(prior_fg)
        if abs(change) >= 5 and not any("F&G" in line for line in notable):
            notable.append(f"F&G {prior_fg} → {current_fg} ({change:+d})")

    prior_nav = (prior.get("portfolio") or {}).get("nav_usd")
    current_nav = (current.get("portfolio") or {}).get("nav_usd")
    nav_change = None
    if prior_nav is not None and current_nav is not None:
        nav_change = round(float(current_nav) - float(prior_nav), 2)
        if abs(nav_change) >= 100 and not any("Portfolio Δ" in line for line in notable):
            notable.append(f"Portfolio Δ ${nav_change:+.2f} since prior snapshot")

    return {
        "prior_as_of": prior_as_of,
        "current_as_of": current_as_of,
        "notable_shifts": notable,
        "portfolio_nav_change_usd": nav_change,
        "fear_greed_change": (
            int(current_fg) - int(prior_fg)
            if prior_fg is not None and current_fg is not None
            else None
        ),
    }
