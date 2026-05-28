from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from alloccontext.ingest.env_keys import optional_env_key
from alloccontext.ingest.parse_helpers import parse_float, parse_int

CMC_BASE = "https://pro-api.coinmarketcap.com/v1"


def _fetch_json(url: str, *, api_key: str, timeout: float) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "alloc-context/0.1",
            "X-CMC_PRO_API_KEY": api_key,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_cmc_global(*, api_key: str, timeout: float) -> dict[str, Any]:
    payload = _fetch_json(f"{CMC_BASE}/global-metrics/quotes/latest", api_key=api_key, timeout=timeout)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ValueError("invalid cmc global payload")
    return data


def fetch_cmc_quotes(
    *,
    symbols: list[str],
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    if not symbols:
        return {}
    query = urllib.parse.urlencode({"symbol": ",".join(symbols), "convert": "USD"})
    payload = _fetch_json(
        f"{CMC_BASE}/cryptocurrency/quotes/latest?{query}",
        api_key=api_key,
        timeout=timeout,
    )
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ValueError("invalid cmc quotes payload")
    return data


def _quote_usd(asset: dict[str, Any]) -> dict[str, Any]:
    quote = (asset.get("quote") or {}).get("USD") or {}
    return quote if isinstance(quote, dict) else {}


def normalize_cmc_snapshot(
    *,
    global_data: dict[str, Any],
    quotes: dict[str, Any],
) -> dict[str, Any]:
    usd = _quote_usd(global_data)
    btc = quotes.get("BTC") or {}
    eth = quotes.get("ETH") or {}
    btc_q = _quote_usd(btc)
    eth_q = _quote_usd(eth)

    return {
        "total_market_cap_usd": _rounded(parse_float(usd.get("total_market_cap"))),
        "btc_dominance_pct": _rounded(parse_float(global_data.get("btc_dominance"))),
        "eth_dominance_pct": _rounded(parse_float(global_data.get("eth_dominance"))),
        "btc_rank": parse_int(btc.get("cmc_rank")),
        "eth_rank": parse_int(eth.get("cmc_rank")),
        "btc_price_usd": _rounded(parse_float(btc_q.get("price"))),
        "eth_price_usd": _rounded(parse_float(eth_q.get("price"))),
        "btc_market_cap_usd": _rounded(parse_float(btc_q.get("market_cap"))),
        "eth_market_cap_usd": _rounded(parse_float(eth_q.get("market_cap"))),
        "btc_change_pct_24h": _rounded(parse_float(btc_q.get("percent_change_24h"))),
        "eth_change_pct_24h": _rounded(parse_float(eth_q.get("percent_change_24h"))),
    }


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def refresh_coinmarketcap(conn, config) -> dict[str, Any]:
    api_key = optional_env_key("COINMARKETCAP_API_KEY")
    if not api_key:
        return {
            "ok": True,
            "rows": 0,
            "skipped": True,
            "reason": "COINMARKETCAP_API_KEY not set",
        }

    try:
        global_data = fetch_cmc_global(api_key=api_key, timeout=config.coinmarketcap.timeout_seconds)
        quotes = fetch_cmc_quotes(
            symbols=list(config.coinmarketcap.symbols),
            api_key=api_key,
            timeout=config.coinmarketcap.timeout_seconds,
        )
        snapshot = normalize_cmc_snapshot(global_data=global_data, quotes=quotes)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return {
                "ok": True,
                "rows": 0,
                "skipped": True,
                "reason": "coinmarketcap_auth_failed",
            }
        if exc.code == 429:
            return {
                "ok": True,
                "rows": 0,
                "skipped": True,
                "reason": "coinmarketcap_rate_limited",
            }
        return {"ok": False, "error": str(exc), "rows": 0}
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc), "rows": 0}

    from alloccontext.ingest.market_snapshots import upsert_crypto_market_snapshot

    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    upsert_crypto_market_snapshot(conn, source="coinmarketcap", snapshot_ts=ts, snapshot=snapshot)
    conn.commit()
    return {"ok": True, "rows": 1, "snapshot_ts": ts, **snapshot}
