from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from alloccontext.ingest.asset_registry import (
    coingecko_ids_for_symbols,
    normalize_canonical_symbol,
    symbols_needing_quotes,
)
from alloccontext.ingest.env_keys import optional_env_key
from alloccontext.ingest.parse_helpers import parse_float


@dataclass(frozen=True)
class QuoteResolverConfig:
    coingecko_api_key: str | None = None
    coinmarketcap_api_key: str | None = None
    timeout_seconds: float = 20.0


def quote_resolver_config_from_env(*, timeout_seconds: float = 20.0) -> QuoteResolverConfig:
    return QuoteResolverConfig(
        coingecko_api_key=optional_env_key("COINGECKO_API_KEY"),
        coinmarketcap_api_key=optional_env_key("COINMARKETCAP_API_KEY"),
        timeout_seconds=timeout_seconds,
    )


def quote_resolver_config_from_app(config) -> QuoteResolverConfig:
    """Build resolver config from ingest app config (timeouts + optional keys)."""
    cg_key = (
        optional_env_key("COINGECKO_API_KEY")
        if config.coingecko.use_demo_key
        else None
    )
    return QuoteResolverConfig(
        coingecko_api_key=cg_key,
        coinmarketcap_api_key=optional_env_key("COINMARKETCAP_API_KEY"),
        timeout_seconds=max(
            config.coingecko.timeout_seconds,
            config.coinmarketcap.timeout_seconds,
        ),
    )


def parse_cmc_symbol_prices(quotes: dict[str, Any]) -> dict[str, float]:
    """Extract symbol → USD price from CMC quotes/latest `data` payload."""
    prices: dict[str, float] = {}
    for payload in quotes.values():
        if not isinstance(payload, dict):
            continue
        raw_symbol = payload.get("symbol")
        if not raw_symbol:
            continue
        quote_block = payload.get("quote")
        if not isinstance(quote_block, dict):
            continue
        quote = quote_block.get("USD") or {}
        if not isinstance(quote, dict):
            continue
        price = parse_float(quote.get("price"))
        if price is not None and price > 0:
            prices[normalize_canonical_symbol(str(raw_symbol))] = float(price)
    return prices


def resolve_balance_prices(
    balances: dict[str, float],
    spot_prices: dict[str, float],
    *,
    exchange_price: Callable[[str], float | None],
    resolver_config: QuoteResolverConfig | None = None,
) -> dict[str, float]:
    """Resolve USD marks: configured spot pairs, exchange ticker, CMC, CoinGecko."""
    prices = {
        normalize_canonical_symbol(symbol): float(value)
        for symbol, value in spot_prices.items()
        if value is not None and float(value) > 0
    }
    missing = [
        symbol
        for symbol in symbols_needing_quotes(balances)
        if symbol not in prices
    ]

    still_missing: list[str] = []
    for symbol in missing:
        mark = exchange_price(symbol)
        if mark is not None and mark > 0:
            prices[symbol] = float(mark)
        else:
            still_missing.append(symbol)

    if not still_missing:
        return prices

    config = resolver_config or quote_resolver_config_from_env()
    still_missing = _apply_cmc_prices(still_missing, prices, config)
    if still_missing:
        _apply_coingecko_prices(still_missing, prices, config)
    return prices


def _apply_cmc_prices(
    symbols: list[str],
    prices: dict[str, float],
    config: QuoteResolverConfig,
) -> list[str]:
    api_key = config.coinmarketcap_api_key
    if not api_key or not symbols:
        return symbols
    try:
        from alloccontext.ingest.coinmarketcap import fetch_cmc_quotes

        quotes = fetch_cmc_quotes(
            symbols=symbols,
            api_key=api_key,
            timeout=config.timeout_seconds,
        )
    except Exception:  # noqa: BLE001
        return symbols
    for symbol, price in parse_cmc_symbol_prices(quotes).items():
        if symbol not in prices:
            prices[symbol] = price
    return [symbol for symbol in symbols if symbol not in prices]


def _apply_coingecko_prices(
    symbols: list[str],
    prices: dict[str, float],
    config: QuoteResolverConfig,
) -> None:
    coin_ids, id_to_symbol = coingecko_ids_for_symbols(symbols)
    if not coin_ids:
        return
    try:
        from alloccontext.ingest.coingecko import fetch_coingecko_simple_prices

        id_prices = fetch_coingecko_simple_prices(
            coin_ids=coin_ids,
            api_key=config.coingecko_api_key,
            timeout=config.timeout_seconds,
        )
    except Exception:  # noqa: BLE001
        return
    for coin_id, price in id_prices.items():
        symbol = id_to_symbol.get(coin_id)
        if symbol and symbol not in prices and price > 0:
            prices[symbol] = price
