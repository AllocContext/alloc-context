from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class KalshiAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class KalshiClient:
    """Read-only Kalshi REST client (public market endpoints)."""

    def __init__(self, base_url: str, *, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not path.startswith("/"):
            path = f"/{path}"
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self.base_url}{path}{query}"
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "alloc-context/0.1"},
            method=method.upper(),
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise KalshiAPIError(
                    f"Kalshi API {method.upper()} {path} failed: {exc.code}",
                    status_code=exc.code,
                ) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                raise KalshiAPIError(f"Kalshi API {method.upper()} {path} failed: {exc}") from exc
            break
        if not body:
            return {}
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {}

    def get_markets(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
        series_ticker: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        if series_ticker:
            params["series_ticker"] = series_ticker
        return self._request("GET", "/markets", params=params)


def dollars_to_cents(value: str | int | float | None) -> int | None:
    if value is None or value == "":
        return None
    return max(1, min(99, round(float(value) * 100)))


def price_cents_from_row(row: dict[str, Any]) -> tuple[int | None, int | None]:
    if row.get("yes_bid") is not None or row.get("yes_ask") is not None:
        bid = row.get("yes_bid")
        ask = row.get("yes_ask")
        return (
            int(bid) if bid is not None else None,
            int(ask) if ask is not None else None,
        )
    return (
        dollars_to_cents(row.get("yes_bid_dollars")),
        dollars_to_cents(row.get("yes_ask_dollars")),
    )


def no_ask_cents_from_row(row: dict[str, Any]) -> int | None:
    if row.get("no_ask") is not None:
        return int(row["no_ask"])
    return dollars_to_cents(row.get("no_ask_dollars"))
