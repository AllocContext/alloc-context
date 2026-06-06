from __future__ import annotations

STABLE_CURRENCIES = frozenset(
    {"USD", "USDC", "USDT", "DAI", "PYUSD", "USDE", "GUSD", "TUSD", "USDD"}
)

# Band assets: full OHLC ingest + ETF flows (see constants.MARKET_VIEW_ASSETS).
BAND_ASSETS = frozenset({"BTC", "ETH"})

# CoinGecko coin IDs for portfolio/market quote fallback (symbol → id).
# Symbols not listed here can still resolve via CoinMarketCap by ticker.
COINGECKO_ID_BY_SYMBOL: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "HYPE": "hyperliquid",
    "POL": "polygon-ecosystem-token",
    "MATIC": "polygon-ecosystem-token",
}

KRAKEN_ASSET_TO_SYMBOL = {
    "XXBT": "BTC",
    "XBT": "BTC",
    "XETH": "ETH",
    "ETH": "ETH",
    "ZUSD": "USD",
    "USD": "USD",
    "USDT": "USD",
    "USDC": "USD",
    "DAI": "USD",
    "PYUSD": "USD",
    "USDE": "USD",
    "TUSD": "USD",
    "USDD": "USD",
    "GUSD": "USD",
}


def normalize_canonical_symbol(symbol: str) -> str:
    return str(symbol).strip().upper()


def is_stable(currency: str) -> bool:
    return normalize_canonical_symbol(currency) in STABLE_CURRENCIES


def kraken_asset_base(asset: str) -> str:
    return asset.split(".", 1)[0]


def kraken_asset_to_symbol(asset: str) -> str | None:
    return KRAKEN_ASSET_TO_SYMBOL.get(kraken_asset_base(asset))


def holding_kind(symbol: str) -> str:
    upper = normalize_canonical_symbol(symbol)
    if upper == "USD" or is_stable(upper):
        return "cash"
    if upper in BAND_ASSETS:
        return "band"
    return "holding"


def symbols_needing_quotes(balances: dict[str, float]) -> list[str]:
    """Non-zero, non-stable balance symbols that may need USD marks."""
    symbols: list[str] = []
    seen: set[str] = set()
    for raw_symbol, qty in balances.items():
        symbol = normalize_canonical_symbol(raw_symbol)
        if qty <= 0 or symbol == "USD" or is_stable(symbol):
            continue
        if symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)
    return symbols


def coingecko_ids_for_symbols(symbols: list[str]) -> tuple[list[str], dict[str, str]]:
    """Return coin IDs to fetch and a reverse map id → canonical symbol."""
    coin_ids: list[str] = []
    id_to_symbol: dict[str, str] = {}
    seen_ids: set[str] = set()
    for raw in symbols:
        symbol = normalize_canonical_symbol(raw)
        coin_id = COINGECKO_ID_BY_SYMBOL.get(symbol)
        if not coin_id or coin_id in seen_ids:
            continue
        coin_ids.append(coin_id)
        id_to_symbol[coin_id] = symbol
        seen_ids.add(coin_id)
    return coin_ids, id_to_symbol
