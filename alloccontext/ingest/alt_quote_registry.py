from __future__ import annotations

import json
import sqlite3

from alloccontext.ingest.asset_registry import (
    BAND_ASSETS,
    is_stable,
    normalize_canonical_symbol,
)
from alloccontext.ingest.alt_quote_store import recent_scope_symbols

DEFAULT_MAX_SCHEDULED_ALT_SYMBOLS = 32


def is_alt_market_symbol(symbol: str) -> bool:
    upper = normalize_canonical_symbol(symbol)
    return upper not in BAND_ASSETS and upper not in {"USD", "CASH"} and not is_stable(upper)


def alt_symbols_from_request(assets: list[str] | None) -> list[str]:
    if not assets:
        return []
    symbols: list[str] = []
    seen: set[str] = set()
    for raw in assets:
        symbol = normalize_canonical_symbol(raw)
        if not symbol or symbol in seen or not is_alt_market_symbol(symbol):
            continue
        symbols.append(symbol)
        seen.add(symbol)
    return symbols


def symbols_from_portfolio(conn: sqlite3.Connection) -> list[str]:
    row = conn.execute(
        """
        SELECT allocation_json FROM portfolio_snapshots
        ORDER BY ts DESC LIMIT 1
        """
    ).fetchone()
    if row is None:
        return []

    allocation = json.loads(row["allocation_json"] or "{}")
    symbols: list[str] = []
    seen: set[str] = set()

    for raw in allocation.get("holdings") or []:
        if not isinstance(raw, dict):
            continue
        symbol = normalize_canonical_symbol(str(raw.get("symbol") or ""))
        if not symbol or symbol in seen or not is_alt_market_symbol(symbol):
            continue
        symbols.append(symbol)
        seen.add(symbol)

    for raw in allocation.get("unrecognized") or []:
        symbol = normalize_canonical_symbol(str(raw))
        if not symbol or symbol in seen or not is_alt_market_symbol(symbol):
            continue
        symbols.append(symbol)
        seen.add(symbol)

    return symbols


def scheduled_alt_symbols(
    conn: sqlite3.Connection,
    *,
    max_symbols: int = DEFAULT_MAX_SCHEDULED_ALT_SYMBOLS,
) -> list[str]:
    """Bounded registry: portfolio alts + recent request scope (LRU)."""
    symbols: list[str] = []
    seen: set[str] = set()
    for symbol in symbols_from_portfolio(conn):
        if symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)
    for symbol in recent_scope_symbols(conn, limit=max_symbols):
        if symbol not in seen and is_alt_market_symbol(symbol):
            symbols.append(symbol)
            seen.add(symbol)
    return symbols[:max_symbols]
