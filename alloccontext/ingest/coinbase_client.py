from __future__ import annotations

import secrets
import time
from typing import Any

import jwt
import requests

from alloccontext.ingest.asset_registry import is_stable
from alloccontext.ingest.exchange_http import should_retry_exchange_attempt
from cryptography.hazmat.primitives import serialization

COINBASE_API = "https://api.coinbase.com"
BROKERAGE_PREFIX = "/api/v3/brokerage"

PRODUCT_TO_SYMBOL = {
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
}

_INTERVAL_TO_GRANULARITY = {
    1: "ONE_MINUTE",
    5: "FIVE_MINUTE",
    15: "FIFTEEN_MINUTE",
    30: "THIRTY_MINUTE",
    60: "ONE_HOUR",
    120: "TWO_HOUR",
    360: "SIX_HOUR",
    1440: "ONE_DAY",
}


def product_to_symbol(product_id: str) -> str:
    product = product_id.upper()
    if product in PRODUCT_TO_SYMBOL:
        return PRODUCT_TO_SYMBOL[product]
    base = product.split("-", 1)[0]
    if base in {"BTC", "ETH"}:
        return base
    return base


def interval_to_granularity(interval_minutes: int) -> str:
    granularity = _INTERVAL_TO_GRANULARITY.get(interval_minutes)
    if granularity is None:
        raise CoinbaseError(f"unsupported_ohlc_interval_minutes:{interval_minutes}")
    return granularity


def normalize_pem_secret(raw: str) -> str:
    secret = raw.strip()
    if "\\n" in secret:
        secret = secret.replace("\\n", "\n")
    return secret


def normalize_coinbase_balances(
    accounts: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, float]]:
    balances: dict[str, float] = {}
    cash_breakdown: dict[str, float] = {}
    for account in accounts:
        currency = str(account.get("currency") or "").upper()
        if not currency:
            continue
        available = float((account.get("available_balance") or {}).get("value") or 0)
        hold = float((account.get("hold") or {}).get("value") or 0)
        total = available + hold
        if total <= 0:
            continue
        if is_stable(currency):
            balances["USD"] = balances.get("USD", 0.0) + total
            cash_breakdown[currency] = cash_breakdown.get(currency, 0.0) + total
        else:
            balances[currency] = balances.get(currency, 0.0) + total
    return balances, cash_breakdown


class CoinbaseError(Exception):
    pass


class CoinbaseClient:
    """Read-only Coinbase Advanced Trade REST client (accounts, product, candles)."""

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        *,
        retry_backoff: float = 2.0,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.api_secret = normalize_pem_secret(api_secret)
        self.retry_backoff = retry_backoff
        self.max_retries = max_retries
        self.session = session or requests.Session()

    def get_ticker(self, product_id: str) -> dict[str, float]:
        data = self._private("GET", f"/market/products/{product_id}")
        price = data.get("price")
        if price is None:
            raise CoinbaseError(f"missing_price:{product_id}")
        last = float(price)
        return {"last": last, "bid": last, "ask": last}

    def get_ohlc(self, product_id: str, interval_minutes: int = 1440) -> list[dict[str, float]]:
        granularity = interval_to_granularity(interval_minutes)
        end = int(time.time())
        start = end - 86400 * 120
        data = self._private(
            "GET",
            f"/market/products/{product_id}/candles",
            params={
                "start": str(start),
                "end": str(end),
                "granularity": granularity,
            },
        )
        candles: list[dict[str, float]] = []
        for row in data.get("candles") or []:
            candles.append(
                {
                    "time": float(row["start"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                }
            )
        candles.sort(key=lambda bar: bar["time"])
        return candles

    def get_balances_with_breakdown(
        self,
    ) -> tuple[dict[str, float], dict[str, float]]:
        if not self.api_key or not self.api_secret:
            raise CoinbaseError(
                "COINBASE_API_KEY and COINBASE_API_SECRET required for balances"
            )
        accounts = self._list_accounts()
        return normalize_coinbase_balances(accounts)

    def _list_accounts(self) -> list[dict[str, Any]]:
        accounts: list[dict[str, Any]] = []
        cursor = ""
        while True:
            params: dict[str, str] = {"limit": "250"}
            if cursor:
                params["cursor"] = cursor
            data = self._private("GET", "/accounts", params=params)
            accounts.extend(data.get("accounts") or [])
            if not data.get("has_next"):
                break
            cursor = str(data.get("cursor") or "")
            if not cursor:
                break
        return accounts

    def _build_jwt(self, method: str, path: str) -> str:
        uri = f"{method} api.coinbase.com{path}"
        private_key = serialization.load_pem_private_key(
            self.api_secret.encode("utf-8"),
            password=None,
        )
        payload = {
            "sub": self.api_key,
            "iss": "cdp",
            "nbf": int(time.time()),
            "exp": int(time.time()) + 120,
            "uri": uri,
        }
        token = jwt.encode(
            payload,
            private_key,
            algorithm="ES256",
            headers={"kid": self.api_key, "nonce": secrets.token_hex()},
        )
        if isinstance(token, bytes):
            return token.decode("utf-8")
        return token

    def _private(
        self,
        method: str,
        subpath: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        path = f"{BROKERAGE_PREFIX}{subpath}"
        return self._request(method, path, params=params, auth=True)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        auth: bool = False,
    ) -> dict[str, Any]:
        url = COINBASE_API + path
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                headers: dict[str, str] = {}
                if auth:
                    headers["Authorization"] = f"Bearer {self._build_jwt(method, path)}"
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
                body = resp.json()
                if not isinstance(body, dict):
                    raise CoinbaseError("invalid_response")
                return body
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt + 1 < self.max_retries and should_retry_exchange_attempt(exc):
                    time.sleep(self.retry_backoff * (attempt + 1))
                    continue
                break
        raise CoinbaseError(str(last_error)) from last_error
