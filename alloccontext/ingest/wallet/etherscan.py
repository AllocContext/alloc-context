from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from alloccontext.ingest.exchange_http import should_retry_exchange_attempt

ETHERSCAN_V2_BASE = "https://api.etherscan.io/v2/api"


class EtherscanError(Exception):
    pass


@dataclass(frozen=True)
class TokenBalanceRow:
    symbol: str
    quantity: float


class EtherscanClient:
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
            raise EtherscanError("etherscan_api_key_required")
        self._api_key = key
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds

    def native_balance_eth(self, chain_id: int, address: str) -> float:
        payload = self._get(
            chain_id=chain_id,
            module="account",
            action="balance",
            address=address,
            tag="latest",
        )
        wei = int(str(payload.get("result") or "0"))
        return wei / 1e18

    def token_balances(self, chain_id: int, address: str) -> list[TokenBalanceRow]:
        payload = self._get(
            chain_id=chain_id,
            module="account",
            action="addresstokenbalance",
            address=address,
            page=1,
            offset=10000,
        )
        rows = payload.get("result") or []
        if not isinstance(rows, list):
            return []
        parsed: list[TokenBalanceRow] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("TokenSymbol") or "").strip()
            if not symbol:
                continue
            qty = _token_quantity(row)
            if qty <= 0:
                continue
            parsed.append(TokenBalanceRow(symbol=symbol, quantity=qty))
        return parsed

    def _get(self, **params: Any) -> dict[str, Any]:
        query = {key: value for key, value in params.items() if value is not None}
        query["apikey"] = self._api_key
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = requests.get(
                    ETHERSCAN_V2_BASE,
                    params=query,
                    timeout=self._timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise EtherscanError("invalid_etherscan_response")
                status = str(payload.get("status") or "")
                message = str(payload.get("message") or "")
                if status == "0" and message.upper() == "NOTOK":
                    result = payload.get("result")
                    detail = str(result) if result is not None else message
                    raise EtherscanError(detail or "etherscan_notok")
                return payload
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt >= self._max_retries or not should_retry_exchange_attempt(exc):
                    break
                time.sleep(self._retry_backoff * (attempt + 1))
        if isinstance(last_exc, EtherscanError):
            raise last_exc
        if last_exc is not None:
            raise EtherscanError(str(last_exc)) from last_exc
        raise EtherscanError("etherscan_request_failed")


def _token_quantity(row: dict[str, Any]) -> float:
    raw_qty = row.get("TokenQuantity")
    divisor = row.get("TokenDivisor")
    try:
        numerator = float(raw_qty)
        denom = 10 ** int(divisor)
    except (TypeError, ValueError):
        return 0.0
    if denom <= 0:
        return 0.0
    return numerator / denom
