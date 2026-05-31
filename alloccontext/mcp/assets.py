from __future__ import annotations

import sqlite3
from typing import Any

from alloccontext.constants import (
    ALLOCATION_ASSETS,
    DEFAULT_VIEW_ASSETS,
    MARKET_VIEW_ASSETS,
)
from alloccontext.ingest.alt_quote_store import has_alt_quote
from alloccontext.ingest.alt_quote_registry import is_alt_market_symbol
from alloccontext.ingest.asset_registry import normalize_canonical_symbol

__all__ = [
    "ALLOCATION_ASSETS",
    "DEFAULT_VIEW_ASSETS",
    "MARKET_VIEW_ASSETS",
    "validate_view_assets",
    "resolve_view_assets",
    "attach_assets_omitted",
    "filter_market_assets",
    "filter_etf_block",
    "filter_delta_market",
    "filter_macro_etf",
    "apply_assets_filter_to_bundle",
    "apply_assets_filter_to_market_payload",
    "market_asset_keys",
]

_SYMBOL_BY_ASSET = {"BTC": "btc", "ETH": "eth", "CASH": "cash"}
_MARKET_VIEW_SET = frozenset(MARKET_VIEW_ASSETS)


def _dedupe_requested(assets: list[str] | None) -> list[str]:
    requested: list[str] = []
    seen: set[str] = set()
    for raw in assets or []:
        key = normalize_canonical_symbol(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        requested.append(key)
    return requested


def resolve_view_assets(
    assets: list[str] | None,
    conn: sqlite3.Connection | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return market filter assets and symbols omitted from market context."""
    if assets is None or len(assets) == 0:
        return DEFAULT_VIEW_ASSETS, ()

    requested = _dedupe_requested(assets)
    supported: list[str] = []
    seen_supported: set[str] = set()
    omitted: list[str] = []

    for key in requested:
        if key in _MARKET_VIEW_SET:
            if key not in seen_supported:
                supported.append(key)
                seen_supported.add(key)
            continue
        if key in ALLOCATION_ASSETS:
            continue
        if is_alt_market_symbol(key):
            if conn is not None and has_alt_quote(conn, key):
                if key not in seen_supported:
                    supported.append(key)
                    seen_supported.add(key)
            else:
                omitted.append(key)

    if supported:
        return tuple(supported), tuple(omitted)
    if omitted:
        return DEFAULT_VIEW_ASSETS, tuple(omitted)
    return DEFAULT_VIEW_ASSETS, ()


def validate_view_assets(
    assets: list[str] | None,
    conn: sqlite3.Connection | None = None,
) -> tuple[str, ...]:
    filter_assets, _ = resolve_view_assets(assets, conn=conn)
    return filter_assets


def attach_assets_omitted(payload: dict[str, Any], omitted: tuple[str, ...]) -> dict[str, Any]:
    if omitted:
        payload["assets_omitted"] = list(omitted)
    return payload


def market_asset_keys(assets: tuple[str, ...]) -> set[str]:
    symbols: set[str] = set()
    for asset in assets:
        key = normalize_canonical_symbol(asset)
        if key in _SYMBOL_BY_ASSET:
            symbols.add(_SYMBOL_BY_ASSET[key])
        elif key and key != "CASH":
            symbols.add(key.lower())
    return symbols


def _asset_symbols(assets: tuple[str, ...]) -> set[str]:
    return market_asset_keys(assets)


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
    wanted = {asset for asset in assets if asset in _MARKET_VIEW_SET}
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
    wanted = {asset for asset in assets if asset in _MARKET_VIEW_SET}
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
