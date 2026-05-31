from __future__ import annotations

import logging
import sqlite3
from typing import Any

from alloccontext.ingest.alt_quote_registry import is_alt_market_symbol, scheduled_alt_symbols
from alloccontext.ingest.alt_quote_store import (
    has_alt_quote,
    upsert_alt_quote_snapshot,
)
from alloccontext.ingest.asset_registry import (
    coingecko_ids_for_symbols,
    normalize_canonical_symbol,
)
from alloccontext.ingest.parse_helpers import parse_float
from alloccontext.ingest.quote_resolver import (
    QuoteResolverConfig,
    parse_cmc_quote_rows,
    quote_resolver_config_from_app,
)
from alloccontext.timeutil import utc_now_iso

logger = logging.getLogger(__name__)


def parse_cmc_alt_quotes(quotes: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract symbol → {price_usd, change_pct_24h, source} from CMC quotes payload."""
    parsed: dict[str, dict[str, Any]] = {}
    for symbol, row in parse_cmc_quote_rows(quotes).items():
        parsed[symbol] = {
            "price_usd": row["price_usd"],
            "change_pct_24h": row.get("change_pct_24h"),
            "source": "coinmarketcap",
        }
    return parsed


def _fetch_alt_quotes(
    symbols: list[str],
    resolver_config: QuoteResolverConfig,
) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}

    remaining = [normalize_canonical_symbol(symbol) for symbol in symbols]
    quotes: dict[str, dict[str, Any]] = {}

    api_key = resolver_config.coinmarketcap_api_key
    if api_key:
        try:
            from alloccontext.ingest.coinmarketcap import fetch_cmc_quotes

            payload = fetch_cmc_quotes(
                symbols=remaining,
                api_key=api_key,
                timeout=resolver_config.timeout_seconds,
            )
            quotes.update(parse_cmc_alt_quotes(payload))
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "coinmarketcap alt quote fetch failed (%s)",
                type(exc).__name__,
            )
    remaining = [symbol for symbol in remaining if symbol not in quotes]
    if not remaining:
        return quotes

    coin_ids, id_to_symbol = coingecko_ids_for_symbols(remaining)
    if coin_ids:
        try:
            from alloccontext.ingest.coingecko import fetch_coingecko_markets

            markets = fetch_coingecko_markets(
                coin_ids=coin_ids,
                api_key=resolver_config.coingecko_api_key,
                timeout=resolver_config.timeout_seconds,
            )
            for row in markets:
                if not isinstance(row, dict):
                    continue
                coin_id = str(row.get("id") or "")
                symbol = id_to_symbol.get(coin_id)
                if not symbol or symbol in quotes:
                    continue
                price = parse_float(row.get("current_price"))
                if price is None or price <= 0:
                    continue
                change = parse_float(row.get("price_change_percentage_24h"))
                quotes[symbol] = {
                    "price_usd": float(price),
                    "change_pct_24h": float(change) if change is not None else None,
                    "source": "coingecko",
                }
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "coingecko markets alt quote fetch failed (%s)",
                type(exc).__name__,
            )

    remaining = [symbol for symbol in remaining if symbol not in quotes]
    if remaining:
        try:
            from alloccontext.ingest.coingecko import fetch_coingecko_simple_prices

            coin_ids, id_to_symbol = coingecko_ids_for_symbols(remaining)
            if coin_ids:
                id_prices = fetch_coingecko_simple_prices(
                    coin_ids=coin_ids,
                    api_key=resolver_config.coingecko_api_key,
                    timeout=resolver_config.timeout_seconds,
                )
                for coin_id, price in id_prices.items():
                    symbol = id_to_symbol.get(coin_id)
                    if symbol and symbol not in quotes and price > 0:
                        quotes[symbol] = {
                            "price_usd": float(price),
                            "change_pct_24h": None,
                            "source": "coingecko",
                        }
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "coingecko simple alt quote fetch failed (%s)",
                type(exc).__name__,
            )

    return quotes


def refresh_alt_quotes(
    conn: sqlite3.Connection,
    config,
    symbols: list[str],
) -> dict[str, Any]:
    """Fetch and persist alt quote snapshots for the requested symbols."""
    alts = [
        normalize_canonical_symbol(symbol)
        for symbol in symbols
        if is_alt_market_symbol(symbol)
    ]
    alts = list(dict.fromkeys(alts))
    if not alts:
        return {"ok": True, "rows": 0, "skipped": True, "reason": "no_alt_symbols"}

    resolver_config = quote_resolver_config_from_app(config)
    if not resolver_config.coinmarketcap_api_key and not resolver_config.coingecko_api_key:
        return {
            "ok": False,
            "rows": 0,
            "skipped": True,
            "reason": "no_quote_api_keys",
            "symbols_requested": alts,
        }

    fetched = _fetch_alt_quotes(alts, resolver_config)
    snapshot_ts = utc_now_iso()
    rows = 0
    for symbol, payload in fetched.items():
        upsert_alt_quote_snapshot(
            conn,
            symbol=symbol,
            snapshot_ts=snapshot_ts,
            price_usd=float(payload["price_usd"]),
            change_pct_24h=payload.get("change_pct_24h"),
            source=str(payload.get("source") or "unknown"),
        )
        rows += 1
    conn.commit()

    missing = [symbol for symbol in alts if symbol not in fetched]
    ok = rows > 0 or not alts
    return {
        "ok": ok,
        "rows": rows,
        "symbols_requested": alts,
        "symbols_fetched": sorted(fetched),
        "symbols_missing": missing,
    }


def refresh_scheduled_alt_quotes(conn: sqlite3.Connection, config) -> dict[str, Any]:
    symbols = scheduled_alt_symbols(conn)
    return refresh_alt_quotes(conn, config, symbols)


def ensure_alt_quotes(
    conn: sqlite3.Connection,
    config,
    symbols: list[str],
) -> dict[str, Any]:
    """Lazy refresh for requested alts that are not yet cached."""
    missing = [
        normalize_canonical_symbol(symbol)
        for symbol in symbols
        if is_alt_market_symbol(symbol) and not has_alt_quote(conn, symbol)
    ]
    missing = list(dict.fromkeys(missing))
    if not missing:
        return {"ok": True, "rows": 0, "skipped": True, "reason": "already_cached"}
    result = refresh_alt_quotes(conn, config, missing)
    if result.get("reason") == "no_quote_api_keys":
        return {**result, "ok": True}
    if not result.get("ok") and int(result.get("rows") or 0) == 0:
        return {**result, "ok": True}
    return result
