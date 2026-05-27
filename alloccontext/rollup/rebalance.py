from __future__ import annotations

from typing import Any

_ASSETS = ("BTC", "ETH", "CASH")


def _round_usd(value: float) -> float:
    return round(value)


def compute_rebalance_plan(
    nav_usd: float,
    current_pct: dict[str, float],
    target_pct: dict[str, float],
    *,
    min_usd: float = 1.0,
) -> dict[str, Any]:
    """USD deltas and Kraken-friendly moves from current to target allocation."""
    if nav_usd <= 0:
        return {"available": False, "reason": "no_nav"}

    current_usd = {a: nav_usd * float(current_pct.get(a) or 0) for a in _ASSETS}
    target_usd = {a: nav_usd * float(target_pct.get(a) or 0) for a in _ASSETS}
    delta_usd = {a: target_usd[a] - current_usd[a] for a in _ASSETS}

    moves: list[str] = []
    cash_surplus = max(0.0, -delta_usd["CASH"])
    crypto_need = {
        "BTC": max(0.0, delta_usd["BTC"]),
        "ETH": max(0.0, delta_usd["ETH"]),
    }
    total_crypto_need = crypto_need["BTC"] + crypto_need["ETH"]

    deployed: dict[str, float] = {"BTC": 0.0, "ETH": 0.0}
    if cash_surplus >= min_usd and total_crypto_need >= min_usd:
        deploy_total = min(cash_surplus, total_crypto_need)
        for asset in ("BTC", "ETH"):
            share = deploy_total * crypto_need[asset] / total_crypto_need
            if share >= min_usd:
                deployed[asset] = share
                moves.append(f"Deploy ~${_round_usd(share):,.0f} from cash → {asset}")

    for asset in ("BTC", "ETH"):
        remaining = delta_usd[asset] - deployed[asset]
        if remaining >= min_usd:
            moves.append(f"Buy ~${_round_usd(remaining):,.0f} more {asset}")
        elif remaining <= -min_usd:
            moves.append(f"Trim ~${_round_usd(-remaining):,.0f} from {asset}")

    if not moves and all(abs(delta_usd[a]) < min_usd for a in _ASSETS):
        moves.append("Already at target within ~$1 rounding.")

    return {
        "available": True,
        "nav_usd": round(nav_usd, 2),
        "current_usd": {a: round(current_usd[a], 2) for a in _ASSETS},
        "target_usd": {a: round(target_usd[a], 2) for a in _ASSETS},
        "delta_usd": {a: round(delta_usd[a], 2) for a in _ASSETS},
        "moves": moves,
    }


def format_rebalance_plan(
    plan: dict[str, Any],
    *,
    target_pct: dict[str, float],
) -> str:
    if not plan.get("available"):
        return ""

    btc = round(float(target_pct.get("BTC") or 0) * 100)
    eth = round(float(target_pct.get("ETH") or 0) * 100)
    cash = round(float(target_pct.get("CASH") or 0) * 100)
    nav = plan.get("nav_usd", 0)
    header = (
        f"**Moves to reach BTC {btc}%, ETH {eth}%, Cash {cash}% "
        f"(~${nav:,.0f} NAV):**"
    )
    bullets = "\n".join(f"- {line}" for line in plan.get("moves") or [])
    return f"{header}\n{bullets}"
