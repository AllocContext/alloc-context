from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from alloccontext.ingest.env_keys import optional_env_key

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


def _fetch_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 20.0) -> Any:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "alloc-context/0.1", **(headers or {})},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"x-cg-demo-api-key": api_key}


def fetch_coingecko_global(*, api_key: str | None, timeout: float) -> dict[str, Any]:
    url = f"{COINGECKO_BASE}/global"
    payload = _fetch_json(url, headers=_headers(api_key), timeout=timeout)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ValueError("invalid coingecko global payload")
    return data


def fetch_coingecko_markets(
    *,
    coin_ids: list[str],
    api_key: str | None,
    timeout: float,
) -> list[dict[str, Any]]:
    if not coin_ids:
        return []
    query = urllib.parse.urlencode(
        {
            "vs_currency": "usd",
            "ids": ",".join(coin_ids),
            "order": "market_cap_desc",
            "sparkline": "false",
        }
    )
    url = f"{COINGECKO_BASE}/coins/markets?{query}"
    payload = _fetch_json(url, headers=_headers(api_key), timeout=timeout)
    if not isinstance(payload, list):
        raise ValueError("invalid coingecko markets payload")
    return [row for row in payload if isinstance(row, dict)]


def normalize_coingecko_snapshot(
    *,
    global_data: dict[str, Any],
    markets: list[dict[str, Any]],
) -> dict[str, Any]:
    market_caps = global_data.get("market_cap_percentage") or {}
    total_cap = (global_data.get("total_market_cap") or {}).get("usd")

    by_id = {str(row.get("id")): row for row in markets}
    btc = by_id.get("bitcoin") or {}
    eth = by_id.get("ethereum") or {}

    return {
        "total_market_cap_usd": _float(total_cap),
        "btc_dominance_pct": _float(market_caps.get("btc")),
        "eth_dominance_pct": _float(market_caps.get("eth")),
        "btc_rank": _int(btc.get("market_cap_rank")),
        "eth_rank": _int(eth.get("market_cap_rank")),
        "btc_price_usd": _float(btc.get("current_price")),
        "eth_price_usd": _float(eth.get("current_price")),
        "btc_market_cap_usd": _float(btc.get("market_cap")),
        "eth_market_cap_usd": _float(eth.get("market_cap")),
        "btc_change_pct_24h": _float(btc.get("price_change_percentage_24h")),
        "eth_change_pct_24h": _float(eth.get("price_change_percentage_24h")),
    }


def refresh_coingecko(conn, config) -> dict[str, Any]:
    api_key = optional_env_key("COINGECKO_API_KEY") if config.coingecko.use_demo_key else None

    def _fetch_snapshot(*, key: str | None) -> dict[str, Any]:
        global_data = fetch_coingecko_global(api_key=key, timeout=config.coingecko.timeout_seconds)
        markets = fetch_coingecko_markets(
            coin_ids=list(config.coingecko.coin_ids),
            api_key=key,
            timeout=config.coingecko.timeout_seconds,
        )
        return normalize_coingecko_snapshot(global_data=global_data, markets=markets)

    try:
        snapshot = _fetch_snapshot(key=api_key)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            return {
                "ok": True,
                "rows": 0,
                "skipped": True,
                "reason": "coingecko_rate_limited",
            }
        if exc.code in (401, 403) and api_key:
            try:
                snapshot = _fetch_snapshot(key=None)
            except urllib.error.HTTPError as retry_exc:
                if retry_exc.code in (401, 403):
                    return {
                        "ok": True,
                        "rows": 0,
                        "skipped": True,
                        "reason": "coingecko_auth_failed",
                    }
                return {"ok": False, "error": str(retry_exc), "rows": 0}
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, RuntimeError) as retry_exc:
                return {"ok": False, "error": str(retry_exc), "rows": 0}
        elif exc.code in (401, 403):
            return {
                "ok": True,
                "rows": 0,
                "skipped": True,
                "reason": "coingecko_auth_failed",
            }
        else:
            return {"ok": False, "error": str(exc), "rows": 0}
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc), "rows": 0}

    from alloccontext.ingest.market_snapshots import upsert_crypto_market_snapshot

    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    upsert_crypto_market_snapshot(conn, source="coingecko", snapshot_ts=ts, snapshot=snapshot)
    return {"ok": True, "rows": 1, "snapshot_ts": ts, **snapshot}


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
