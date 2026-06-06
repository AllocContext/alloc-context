from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from alloccontext.ingest.exchange_http import should_retry_exchange_attempt
from alloccontext.ingest.wallet.curated_tokens import CuratedToken, curated_tokens_for_chain

ETHERSCAN_V2_BASE = "https://api.etherscan.io/v2/api"
# Free tier allows ~3 calls/sec; stay under with a fixed gap between requests.
_MIN_REQUEST_INTERVAL_SECONDS = 0.34


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
        self._last_request_at = 0.0

    def native_balance_eth(self, chain_id: int, address: str) -> float:
        payload = self._get(
            chain_id,
            module="account",
            action="balance",
            address=address,
            tag="latest",
        )
        wei = int(str(payload.get("result") or "0"))
        return wei / 1e18

    def token_balance(
        self,
        chain_id: int,
        address: str,
        token: CuratedToken,
    ) -> float:
        payload = self._get(
            chain_id,
            module="account",
            action="tokenbalance",
            contractaddress=token.contract,
            address=address,
            tag="latest",
        )
        raw = int(str(payload.get("result") or "0"))
        if raw <= 0:
            return 0.0
        return raw / (10**token.decimals)

    def curated_token_balances(self, chain_id: int, address: str) -> list[TokenBalanceRow]:
        parsed: list[TokenBalanceRow] = []
        for token in curated_tokens_for_chain(chain_id):
            qty = self.token_balance(chain_id, address, token)
            if qty <= 0:
                continue
            parsed.append(TokenBalanceRow(symbol=token.symbol, quantity=qty))
        return parsed

    def _get(self, chain_id: int, **params: Any) -> dict[str, Any]:
        query: dict[str, Any] = {"chainid": chain_id}
        query.update({key: value for key, value in params.items() if value is not None})
        query["apikey"] = self._api_key
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                self._throttle()
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
                if attempt >= self._max_retries or not _should_retry_etherscan(exc):
                    break
                time.sleep(self._retry_backoff * (attempt + 1))
        if isinstance(last_exc, EtherscanError):
            raise last_exc
        if last_exc is not None:
            raise EtherscanError(str(last_exc)) from last_exc
        raise EtherscanError("etherscan_request_failed")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request_at = time.monotonic()


def _should_retry_etherscan(exc: Exception) -> bool:
    if isinstance(exc, EtherscanError):
        detail = str(exc).lower()
        if "rate limit" in detail or "max calls per sec" in detail:
            return True
    return should_retry_exchange_attempt(exc)
