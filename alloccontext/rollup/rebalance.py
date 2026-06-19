from __future__ import annotations

from typing import Any

from alloccontext.ingest.asset_registry import is_stable

CASH_SYMBOL = "CASH"


def _round_usd(value: float) -> float:
    return round(value)


def _normalize_symbol(symbol: str) -> str:
    return str(symbol).strip().upper()


def _is_cash_symbol(symbol: str) -> bool:
    sym = _normalize_symbol(symbol)
    return sym in {CASH_SYMBOL, "USD"} or is_stable(sym)


def collapse_cash_weights(allocation_pct: dict[str, float]) -> dict[str, float]:
    """Merge USD/stables into CASH; keep other symbols keyed by canonical symbol."""
    weights: dict[str, float] = {}
    cash = 0.0
    for key, raw in allocation_pct.items():
        sym = _normalize_symbol(key)
        if not sym:
            continue
        value = float(raw)
        if _is_cash_symbol(sym):
            cash += value
        else:
            weights[sym] = weights.get(sym, 0.0) + value
    if cash > 0:
        weights[CASH_SYMBOL] = weights.get(CASH_SYMBOL, 0.0) + cash
    return weights


def _target_symbols(target_pct: dict[str, float]) -> list[str]:
    return sorted(_normalize_symbol(key) for key in target_pct if _normalize_symbol(key))


def _product_for_asset(exchange: str, asset: str, pairs: dict[str, str] | None) -> str:
    if pairs and asset in pairs:
        return pairs[asset]
    exchange_key = exchange.strip().lower()
    if exchange_key == "coinbase":
        if asset == "BTC":
            return "BTC-USD"
        return f"{asset}-USD"
    if asset == "BTC":
        return "XBTUSD"
    if asset == "ETH":
        return "ETHUSD"
    return f"{asset}USD"


def _kraken_display_symbol(asset: str) -> str:
    return "XBT" if asset == "BTC" else asset


def _buy_move(exchange: str, asset: str, usd: float, pairs: dict[str, str] | None) -> str:
    amount = _round_usd(usd)
    if exchange == "coinbase":
        product = _product_for_asset(exchange, asset, pairs)
        return f"Buy ~${amount:,.0f} {asset} on {product}"
    pair = _product_for_asset(exchange, asset, pairs)
    symbol = _kraken_display_symbol(asset)
    return f"Buy ~${amount:,.0f} {symbol} ({pair})"


def _trim_move(exchange: str, asset: str, usd: float, pairs: dict[str, str] | None) -> str:
    amount = _round_usd(usd)
    if exchange == "coinbase":
        product = _product_for_asset(exchange, asset, pairs)
        return f"Sell ~${amount:,.0f} {asset} on {product}"
    pair = _product_for_asset(exchange, asset, pairs)
    symbol = _kraken_display_symbol(asset)
    return f"Sell ~${amount:,.0f} {symbol} ({pair})"


def _deploy_move(exchange: str, asset: str, usd: float, pairs: dict[str, str] | None) -> str:
    amount = _round_usd(usd)
    if exchange == "coinbase":
        product = _product_for_asset(exchange, asset, pairs)
        return f"Deploy ~${amount:,.0f} from USD → {asset} on {product}"
    symbol = _kraken_display_symbol(asset)
    return f"Deploy ~${amount:,.0f} from cash → {symbol}"


def format_target_pct_header(target_pct: dict[str, float]) -> str:
    labels: list[str] = []
    symbols = sorted(
        _normalize_symbol(key) for key in target_pct if _normalize_symbol(key)
    )
    for symbol in symbols:
        pct = round(float(target_pct.get(symbol) or target_pct.get(symbol.lower()) or 0) * 100)
        label = "Cash" if symbol == CASH_SYMBOL else symbol
        labels.append(f"{label} {pct}%")
    return ", ".join(labels)


def compute_rebalance_plan(
    nav_usd: float,
    current_pct: dict[str, float],
    target_pct: dict[str, float],
    *,
    min_usd: float = 1.0,
    exchange: str = "kraken",
    pairs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """USD deltas and exchange-style moves from current to target allocation."""
    if nav_usd <= 0:
        return {"available": False, "reason": "no_nav"}

    symbols = _target_symbols(target_pct)
    if not symbols:
        return {"available": False, "reason": "empty_target"}

    exchange_key = exchange.strip().lower() if exchange else "kraken"
    current = collapse_cash_weights(current_pct)
    target = collapse_cash_weights(target_pct)

    current_usd: dict[str, float] = {}
    target_usd: dict[str, float] = {}
    delta_usd: dict[str, float] = {}
    for symbol in symbols:
        current_weight = float(current.get(symbol) or 0)
        target_weight = float(target.get(symbol) or 0)
        current_usd[symbol] = round(nav_usd * current_weight, 2)
        target_usd[symbol] = round(nav_usd * target_weight, 2)
        delta_usd[symbol] = round(target_usd[symbol] - current_usd[symbol], 2)

    moves: list[str] = []
    deployed = {symbol: 0.0 for symbol in symbols if symbol != CASH_SYMBOL}

    cash_surplus = max(0.0, -float(delta_usd.get(CASH_SYMBOL) or 0))
    buy_need = {
        symbol: max(0.0, delta_usd[symbol])
        for symbol in symbols
        if symbol != CASH_SYMBOL and delta_usd[symbol] > 0
    }
    total_buy_need = sum(buy_need.values())

    if cash_surplus >= min_usd and total_buy_need >= min_usd:
        deploy_total = min(cash_surplus, total_buy_need)
        for symbol, need in buy_need.items():
            share = deploy_total * need / total_buy_need
            if share >= min_usd:
                deployed[symbol] = deployed.get(symbol, 0.0) + share
                moves.append(_deploy_move(exchange_key, symbol, share, pairs))

    for symbol in symbols:
        if symbol == CASH_SYMBOL:
            continue
        remaining = delta_usd[symbol] - deployed.get(symbol, 0.0)
        if remaining >= min_usd:
            moves.append(_buy_move(exchange_key, symbol, remaining, pairs))
        elif remaining <= -min_usd:
            moves.append(_trim_move(exchange_key, symbol, -remaining, pairs))

    if not moves and all(abs(delta_usd[symbol]) < min_usd for symbol in symbols):
        moves.append("Already at target within ~$1 rounding.")

    return {
        "available": True,
        "exchange": exchange_key,
        "nav_usd": round(nav_usd, 2),
        "current_usd": current_usd,
        "target_usd": target_usd,
        "delta_usd": delta_usd,
        "moves": moves,
    }


def format_rebalance_plan(
    plan: dict[str, Any],
    *,
    target_pct: dict[str, float],
) -> str:
    if not plan.get("available"):
        return ""

    nav = plan.get("nav_usd", 0)
    header = (
        f"**Moves to reach {format_target_pct_header(target_pct)} "
        f"(~${nav:,.0f} NAV):**"
    )
    bullets = "\n".join(f"- {line}" for line in plan.get("moves") or [])
    return f"{header}\n{bullets}"
