from __future__ import annotations

from typing import Any, Callable

from alloccontext.constants import ALLOCATION_ASSETS
from alloccontext.ingest.asset_registry import BAND_ASSETS, holding_kind, is_stable


def band_allocation_pct(holdings: list[dict[str, Any]]) -> dict[str, float]:
    weights = {asset: 0.0 for asset in ALLOCATION_ASSETS}
    for row in holdings:
        symbol = str(row.get("symbol") or "").upper()
        weight = row.get("weight_pct")
        if weight is None:
            continue
        if symbol in BAND_ASSETS:
            weights[symbol] = float(weight)
        elif symbol in {"USD", "CASH"} or is_stable(symbol):
            weights["CASH"] += float(weight)
    return weights


def build_holdings(
    balances: dict[str, float],
    prices: dict[str, float],
    *,
    cash_breakdown: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    unrecognized: list[str] = []
    rows: list[dict[str, Any]] = []
    asset_values: dict[str, float] = {}
    cash_usd = float(balances.get("USD") or 0)

    for symbol, qty in sorted(balances.items()):
        if symbol == "USD" or qty <= 0:
            continue
        price = prices.get(symbol)
        if price is None:
            unrecognized.append(symbol)
            rows.append(
                {
                    "symbol": symbol,
                    "qty": round(qty, 8),
                    "price_usd": None,
                    "value_usd": None,
                    "weight_pct": None,
                    "kind": holding_kind(symbol),
                }
            )
            continue
        value = qty * price
        asset_values[symbol] = value
        rows.append(
            {
                "symbol": symbol,
                "qty": round(qty, 8),
                "price_usd": round(price, 8),
                "value_usd": round(value, 2),
                "weight_pct": None,
                "kind": holding_kind(symbol),
            }
        )

    total = cash_usd + sum(asset_values.values())
    if total > 0:
        for row in rows:
            symbol = row["symbol"]
            if symbol in asset_values:
                row["weight_pct"] = round(asset_values[symbol] / total, 4)

    if cash_usd > 0:
        cash_row: dict[str, Any] = {
            "symbol": "USD",
            "qty": round(cash_usd, 2),
            "price_usd": 1.0,
            "value_usd": round(cash_usd, 2),
            "weight_pct": round(cash_usd / total, 4) if total > 0 else None,
            "kind": "cash",
        }
        if cash_breakdown:
            cash_row["cash_breakdown"] = {
                key: round(value, 2) for key, value in cash_breakdown.items()
            }
        rows.append(cash_row)

    rows.sort(key=lambda row: (-(row.get("value_usd") or 0), row["symbol"]))
    return rows, unrecognized


def resolve_prices_for_balances(
    balances: dict[str, float],
    spot_prices: dict[str, float],
    *,
    fetch_price: Callable[[str], float | None],
) -> dict[str, float]:
    prices = dict(spot_prices)
    for symbol, qty in balances.items():
        if qty <= 0 or symbol == "USD" or is_stable(symbol):
            continue
        if symbol in prices:
            continue
        mark = fetch_price(symbol)
        if mark is not None:
            prices[symbol] = mark
    return prices


def legacy_holdings_from_allocation(
    allocation: dict[str, Any],
    *,
    nav_usd: float,
    cash_usd: float,
) -> list[dict[str, Any]]:
    prices = allocation.get("prices") or {}
    stored = allocation.get("holdings")
    if isinstance(stored, list) and stored:
        return list(stored)

    rows: list[dict[str, Any]] = []
    for symbol in ("BTC", "ETH"):
        pct = float(allocation.get(symbol) or 0)
        if pct <= 0:
            continue
        value = nav_usd * pct
        price = prices.get(symbol)
        qty = value / price if price else 0.0
        rows.append(
            {
                "symbol": symbol,
                "qty": round(qty, 8),
                "price_usd": round(price, 8) if price else None,
                "value_usd": round(value, 2),
                "weight_pct": round(pct, 4),
                "kind": "band",
            }
        )
    if cash_usd > 0:
        cash_pct = float(allocation.get("CASH") or 0)
        cash_row: dict[str, Any] = {
            "symbol": "USD",
            "qty": round(cash_usd, 2),
            "price_usd": 1.0,
            "value_usd": round(cash_usd, 2),
            "weight_pct": round(cash_pct, 4) if cash_pct else None,
            "kind": "cash",
        }
        breakdown = allocation.get("cash_breakdown")
        if breakdown:
            cash_row["cash_breakdown"] = breakdown
        rows.append(cash_row)
    return rows
