from __future__ import annotations

STABLE_CURRENCIES = frozenset(
    {"USD", "USDC", "USDT", "DAI", "PYUSD", "USDE", "GUSD", "TUSD", "USDD"}
)

BAND_ASSETS = frozenset({"BTC", "ETH"})

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


def is_stable(currency: str) -> bool:
    return currency.upper() in STABLE_CURRENCIES


def kraken_asset_base(asset: str) -> str:
    return asset.split(".", 1)[0]


def kraken_asset_to_symbol(asset: str) -> str | None:
    return KRAKEN_ASSET_TO_SYMBOL.get(kraken_asset_base(asset))


def holding_kind(symbol: str) -> str:
    upper = symbol.upper()
    if upper == "USD" or is_stable(upper):
        return "cash"
    if upper in BAND_ASSETS:
        return "band"
    return "holding"
