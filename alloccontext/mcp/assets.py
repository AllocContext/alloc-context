from __future__ import annotations

from typing import Any

from alloccontext.constants import ALLOCATION_ASSETS, DEFAULT_VIEW_ASSETS

__all__ = [
    "ALLOCATION_ASSETS",
    "DEFAULT_VIEW_ASSETS",
    "validate_view_assets",
    "filter_market_assets",
    "filter_etf_block",
    "filter_delta_market",
    "filter_macro_etf",
    "apply_assets_filter_to_bundle",
    "apply_assets_filter_to_market_payload",
]

_SYMBOL_BY_ASSET = {"BTC": "btc", "ETH": "eth", "CASH": "cash"}


def validate_view_assets(assets: list[str] | None) -> tuple[str, ...]:
    if assets is None or len(assets) == 0:
        return DEFAULT_VIEW_ASSETS
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in assets:
        key = str(raw).strip().upper()
        if not key:
            continue
        if key not in ALLOCATION_ASSETS:
            raise ValueError(
                f"unsupported asset {raw!r}; allowed: {', '.join(ALLOCATION_ASSETS)}"
            )
        if key not in seen:
            normalized.append(key)
            seen.add(key)
    if not normalized:
        return DEFAULT_VIEW_ASSETS
    return tuple(normalized)


def _asset_symbols(assets: tuple[str, ...]) -> set[str]:
    return {_SYMBOL_BY_ASSET[asset] for asset in assets if asset in _SYMBOL_BY_ASSET}


def filter_market_assets(market: dict[str, Any], assets: tuple[str, ...]) -> dict[str, Any]:
    if not market.get("available"):
        return market
    symbols = _asset_symbols(assets)
    block = market.get("assets")
    if not isinstance(block, dict) or not symbols:
        return market
    filtered = {
        key: value for key, value in block.items() if key.lower() in symbols
    }
    result = dict(market)
    if filtered:
        result["assets"] = filtered
    else:
        result["available"] = False
        result["reason"] = "no_market_data_for_requested_assets"
        result.pop("assets", None)
    return result


def filter_etf_block(etf: dict[str, Any], assets: tuple[str, ...]) -> dict[str, Any]:
    if not etf.get("available"):
        return etf
    block = etf.get("assets")
    if not isinstance(block, dict):
        return etf
    wanted = {asset for asset in assets if asset in ("BTC", "ETH")}
    if not wanted:
        return etf
    filtered = {key: value for key, value in block.items() if key.upper() in wanted}
    result = dict(etf)
    if filtered:
        result["assets"] = filtered
    else:
        result["available"] = False
        result["reason"] = "no_etf_data_for_requested_assets"
        result.pop("assets", None)
    return result


def filter_delta_market(delta: dict[str, Any], assets: tuple[str, ...]) -> dict[str, Any]:
    if not delta.get("available"):
        return delta
    symbols = _asset_symbols(assets)
    shifts = [
        line
        for line in delta.get("notable_shifts") or []
        if any(symbol.upper() in line for symbol in symbols)
        or "Portfolio" in line
        or "F&G" in line
    ]
    result = dict(delta)
    result["notable_shifts"] = shifts
    market = delta.get("market")
    if not isinstance(market, dict):
        return result
    filtered_market = {
        key: value
        for key, value in market.items()
        if any(symbol in key for symbol in symbols)
    }
    if filtered_market:
        result["market"] = filtered_market
    else:
        result.pop("market", None)
    return result


def filter_macro_etf(macro: dict[str, Any], assets: tuple[str, ...]) -> dict[str, Any]:
    etf = macro.get("etf")
    if not isinstance(etf, dict):
        return macro
    wanted = {asset for asset in assets if asset in ("BTC", "ETH")}
    if not wanted:
        return macro
    filtered = {key: value for key, value in etf.items() if key.upper() in wanted}
    result = dict(macro)
    if filtered:
        result["etf"] = filtered
    else:
        result.pop("etf", None)
    return result


def apply_assets_filter_to_bundle(
    bundle: dict[str, Any],
    assets: tuple[str, ...],
) -> dict[str, Any]:
    result = dict(bundle)
    result["assets"] = list(assets)
    if "market" in result:
        result["market"] = filter_market_assets(result["market"], assets)
    if "macro" in result and isinstance(result["macro"], dict):
        result["macro"] = filter_macro_etf(result["macro"], assets)
    if "delta" in result:
        result["delta"] = filter_delta_market(result["delta"], assets)
    return result


def apply_assets_filter_to_market_payload(
    payload: dict[str, Any],
    assets: tuple[str, ...],
) -> dict[str, Any]:
    result = dict(payload)
    result["assets"] = list(assets)
    if isinstance(result.get("etf"), dict):
        result["etf"] = filter_etf_block(result["etf"], assets)
    if isinstance(result.get("breadth"), dict) and isinstance(
        result["breadth"].get("assets"), dict
    ):
        symbols = _asset_symbols(assets)
        breadth = dict(result["breadth"])
        breadth["assets"] = {
            key: value
            for key, value in breadth["assets"].items()
            if key.lower() in symbols
        }
        result["breadth"] = breadth
    return result
