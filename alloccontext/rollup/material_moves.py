"""Portfolio-scoped material market moves (ADR-020 — sleeve, not regime)."""

from __future__ import annotations

from typing import Any

from alloccontext.ingest.asset_registry import BAND_ASSETS, is_stable, normalize_canonical_symbol

_MATERIAL_WEIGHT_THRESHOLD = 0.10
_MATERIAL_MOVE_THRESHOLD_PCT = 5.0


def build_portfolio_material_moves(
    *,
    portfolio: dict[str, Any],
    market: dict[str, Any],
    delta: dict[str, Any],
) -> list[dict[str, str]]:
    """Held alts with large market moves — attached to portfolio, not regime."""
    if not portfolio.get("available"):
        return []

    market_assets = market.get("assets") if market.get("available") else {}
    if not isinstance(market_assets, dict):
        market_assets = {}
    market_changes = delta.get("market") if delta.get("available") else {}
    if not isinstance(market_changes, dict):
        market_changes = {}

    moves: list[dict[str, str]] = []
    for row in portfolio.get("holdings") or []:
        if not isinstance(row, dict):
            continue
        symbol = normalize_canonical_symbol(str(row.get("symbol") or ""))
        if not symbol or symbol in BAND_ASSETS or symbol in {"USD", "CASH"} or is_stable(symbol):
            continue
        weight = row.get("weight_pct")
        if weight is None or float(weight) < _MATERIAL_WEIGHT_THRESHOLD:
            continue

        key = symbol.lower()
        block = market_assets.get(key) if isinstance(market_assets.get(key), dict) else {}
        move = (block.get("change_pct") or {}).get("24h") if isinstance(block, dict) else None
        if move is None:
            move = market_changes.get(f"{key}_change_pct_since_prior")

        if move is None or abs(float(move)) < _MATERIAL_MOVE_THRESHOLD_PCT:
            continue

        move_f = float(move)
        moves.append(
            {
                "symbol": symbol,
                "weight_pct": float(weight),
                "move_pct": move_f,
                "text": (
                    f"{symbol} ({float(weight) * 100:.1f}% weight) moved "
                    f"{move_f:+.1f}% — material for portfolio."
                ),
            }
        )
    return moves
