from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any

import requests

KRAKEN_API = "https://api.kraken.com"

ASSET_TO_SYMBOL = {
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

PAIR_TO_SYMBOL = {
    "XBTUSD": "BTC",
    "XXBTZUSD": "BTC",
    "ETHUSD": "ETH",
    "XETHZUSD": "ETH",
}


def pair_to_symbol(pair: str) -> str:
    return PAIR_TO_SYMBOL.get(pair.upper(), pair.replace("USD", "").replace("XBT", "BTC"))


def _kraken_asset_base(asset: str) -> str:
    return asset.split(".", 1)[0]


def normalize_kraken_balances(raw: dict[str, Any]) -> dict[str, float]:
    balances: dict[str, float] = {"BTC": 0.0, "ETH": 0.0, "USD": 0.0}
    for asset, amount in raw.items():
        symbol = ASSET_TO_SYMBOL.get(_kraken_asset_base(asset))
        if symbol:
            balances[symbol] = balances.get(symbol, 0.0) + float(amount)
    return balances


def cash_breakdown_from_raw(raw: dict[str, Any]) -> dict[str, float]:
    breakdown: dict[str, float] = {}
    for asset, amount in raw.items():
        base = _kraken_asset_base(asset)
        if ASSET_TO_SYMBOL.get(base) != "USD":
            continue
        value = float(amount)
        if value <= 0:
            continue
        breakdown[base] = breakdown.get(base, 0.0) + value
    return breakdown


class KrakenError(Exception):
    pass


class KrakenClient:
    """Read-only Kraken REST client (balances, ticker, OHLC)."""

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
        self.api_secret = api_secret.strip()
        self.retry_backoff = retry_backoff
        self.max_retries = max_retries
        self.session = session or requests.Session()

    def get_ticker(self, pair: str) -> dict[str, float]:
        data = self._public("Ticker", {"pair": pair})
        key = next(iter(data))
        ticker = data[key]
        return {
            "last": float(ticker["c"][0]),
            "bid": float(ticker["b"][0]),
            "ask": float(ticker["a"][0]),
        }

    def get_ohlc(self, pair: str, interval: int = 1440) -> list[dict[str, float]]:
        data = self._public("OHLC", {"pair": pair, "interval": interval})
        key = next(k for k in data if k != "last")
        candles: list[dict[str, float]] = []
        for row in data[key]:
            candles.append(
                {
                    "time": float(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                }
            )
        return candles

    def get_balances_with_breakdown(
        self,
    ) -> tuple[dict[str, float], dict[str, float]]:
        if not self.api_key or not self.api_secret:
            raise KrakenError("KRAKEN_API_KEY and KRAKEN_API_SECRET required for balances")
        raw = self._private("Balance")
        return normalize_kraken_balances(raw), cash_breakdown_from_raw(raw)

    def _public(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", f"/0/public/{path}", params=params)

    def _private(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", f"/0/private/{path}", data=params or {})

    @staticmethod
    def _sign(private_path: str, payload: dict[str, Any], api_secret: str) -> str:
        post_data = urllib.parse.urlencode(payload)
        nonce = str(payload["nonce"])
        encoded = (nonce + post_data).encode()
        message = private_path.encode() + hashlib.sha256(encoded).digest()
        secret = base64.b64decode(api_secret)
        digest = hmac.new(secret, message, hashlib.sha512).digest()
        return base64.b64encode(digest).decode()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = KRAKEN_API + path
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                headers: dict[str, str] = {}
                if path.startswith("/0/private"):
                    nonce = str(int(time.time() * 1000))
                    payload = {"nonce": nonce, **(data or {})}
                    headers = {
                        "API-Key": self.api_key,
                        "API-Sign": self._sign(path, payload, self.api_secret),
                    }
                    resp = self.session.post(url, data=payload, headers=headers, timeout=30)
                else:
                    resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                body = resp.json()
                if body.get("error"):
                    raise KrakenError("; ".join(body["error"]))
                return body["result"]
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_backoff * (attempt + 1))
        raise KrakenError(str(last_error)) from last_error
