from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from alloccontext.ingest.exchange_http import should_retry_exchange_attempt
from alloccontext.ingest.wallet.chains import alchemy_networks_for_chain_ids

ALCHEMY_DATA_BASE = "https://api.g.alchemy.com/data/v1"

# Native token metadata is often null; map network slug → band symbol.
NATIVE_SYMBOL_BY_NETWORK: dict[str, str] = {
    "eth-mainnet": "ETH",
    "arb-mainnet": "ETH",
    "base-mainnet": "ETH",
    "opt-mainnet": "ETH",
    "polygon-mainnet": "POL",
    "matic-mainnet": "POL",
}


class AlchemyError(Exception):
    pass


@dataclass(frozen=True)
class AlchemyTokenRow:
    symbol: str
    quantity: float
    price_usd: float | None = None
    is_native: bool = False
    token_address: str | None = None


class AlchemyClient:
    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 2.0,
    ) -> None:
        key = api_key.strip()
        if not key:
            raise AlchemyError("alchemy_api_key_required")
        self._api_key = key
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds

    def token_balances(
        self,
        address: str,
        chain_ids: tuple[int, ...],
    ) -> list[AlchemyTokenRow]:
        networks = alchemy_networks_for_chain_ids(chain_ids)
        url = f"{ALCHEMY_DATA_BASE}/{self._api_key}/assets/tokens/by-address"
        rows: list[AlchemyTokenRow] = []
        page_key: str | None = None
        while True:
            payload = self._post(
                url,
                {
                    "addresses": [{"address": address, "networks": list(networks)}],
                    "includeNativeTokens": True,
                    "includeErc20Tokens": True,
                    "withMetadata": True,
                    "withPrices": True,
                    **({"pageKey": page_key} if page_key else {}),
                },
            )
            data = payload.get("data") or {}
            tokens = data.get("tokens") or []
            if not isinstance(tokens, list):
                break
            for token in tokens:
                parsed = _parse_token_row(token)
                if parsed is not None:
                    rows.append(parsed)
            page_key = data.get("pageKey")
            if not page_key:
                break
        return rows

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = requests.post(
                    url,
                    json=body,
                    headers={"Content-Type": "application/json"},
                    timeout=self._timeout,
                )
                if response.status_code == 429:
                    raise AlchemyError("alchemy_rate_limit")
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise AlchemyError("invalid_alchemy_response")
                if payload.get("error"):
                    message = str((payload.get("error") or {}).get("message") or payload)
                    raise AlchemyError(message)
                return payload
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt >= self._max_retries or not _should_retry_alchemy(exc):
                    break
                time.sleep(self._retry_backoff * (attempt + 1))
        if isinstance(last_exc, AlchemyError):
            raise last_exc
        if last_exc is not None:
            raise AlchemyError(str(last_exc)) from last_exc
        raise AlchemyError("alchemy_request_failed")


def _should_retry_alchemy(exc: Exception) -> bool:
    if isinstance(exc, AlchemyError):
        detail = str(exc).lower()
        if "rate limit" in detail or "rate_limit" in detail:
            return True
    return should_retry_exchange_attempt(exc)


def _parse_token_row(token: dict[str, Any]) -> AlchemyTokenRow | None:
    if not isinstance(token, dict):
        return None
    network = str(token.get("network") or "")
    token_address = token.get("tokenAddress")
    is_native = not token_address
    metadata = token.get("tokenMetadata") or {}
    symbol = str(metadata.get("symbol") or "").strip()
    if not symbol:
        symbol = NATIVE_SYMBOL_BY_NETWORK.get(network, "")
    if not symbol or len(symbol) > 20:
        return None
    decimals = metadata.get("decimals")
    if is_native:
        decimals_int = 18
    else:
        if decimals is None:
            return None
        try:
            decimals_int = int(decimals)
        except (TypeError, ValueError):
            return None
    quantity = _parse_hex_balance(str(token.get("tokenBalance") or "0x0"), decimals_int)
    if quantity <= 0:
        return None
    price_usd = _price_usd_per_unit(token.get("tokenPrices"))
    contract = str(token_address).lower() if token_address else None
    return AlchemyTokenRow(
        symbol=symbol,
        quantity=quantity,
        price_usd=price_usd,
        is_native=is_native,
        token_address=contract,
    )


def _parse_hex_balance(raw: str, decimals: int) -> float:
    if not raw or raw in {"0x", "0x0"}:
        return 0.0
    try:
        amount = int(raw, 16)
    except ValueError:
        return 0.0
    if amount <= 0:
        return 0.0
    return amount / (10**decimals)


def _price_usd_per_unit(token_prices: Any) -> float | None:
    if not isinstance(token_prices, list):
        return None
    for row in token_prices:
        if not isinstance(row, dict):
            continue
        if str(row.get("currency") or "").lower() != "usd":
            continue
        try:
            value = float(row.get("value"))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None
