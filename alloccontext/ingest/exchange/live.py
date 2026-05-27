from __future__ import annotations

from typing import Any

from alloccontext.ingest.coinbase_client import CoinbaseClient, CoinbaseError
from alloccontext.ingest.coinbase_portfolio import fetch_portfolio_snapshot as fetch_coinbase_snapshot
from alloccontext.ingest.exchange.types import ExchangeId
from alloccontext.ingest.kraken_client import KrakenClient, KrakenError
from alloccontext.ingest.kraken_portfolio import (
    PortfolioSnapshot,
    fetch_portfolio_snapshot as fetch_kraken_snapshot,
)

SUPPORTED_EXCHANGES = frozenset({"kraken", "coinbase"})


class LivePortfolioError(Exception):
    pass


def validate_exchange_id(exchange: str) -> ExchangeId:
    key = exchange.strip().lower()
    if key not in SUPPORTED_EXCHANGES:
        raise ValueError(f"unsupported exchange: {exchange}")
    return key  # type: ignore[return-value]


def _spot_config(config, exchange_id: ExchangeId):
    if exchange_id == "kraken":
        return config.exchanges.kraken
    return config.exchanges.coinbase


def fetch_live_portfolio_snapshot(
    exchange_id: ExchangeId,
    api_key: str,
    api_secret: str,
    config,
) -> PortfolioSnapshot:
    spot = _spot_config(config, exchange_id)
    key = api_key.strip()
    secret = api_secret.strip()
    if not key or not secret:
        raise LivePortfolioError("api_key and api_secret are required")

    try:
        if exchange_id == "kraken":
            client = KrakenClient(
                api_key=key,
                api_secret=secret,
                retry_backoff=spot.retry_backoff_seconds,
                max_retries=spot.max_retries,
            )
            return fetch_kraken_snapshot(client, spot)
        client = CoinbaseClient(
            api_key=key,
            api_secret=secret,
            retry_backoff=spot.retry_backoff_seconds,
            max_retries=spot.max_retries,
        )
        return fetch_coinbase_snapshot(client, spot)
    except (KrakenError, CoinbaseError) as exc:
        raise LivePortfolioError(str(exc)) from exc


def portfolio_state_from_snapshot(
    snap: PortfolioSnapshot,
    *,
    exchange_id: ExchangeId,
    target_pct: dict[str, float],
    band: float,
) -> dict[str, Any]:
    from alloccontext.rollup.band import check_allocation_band

    allocation_pct = {
        "BTC": snap.btc_pct,
        "ETH": snap.eth_pct,
        "CASH": snap.cash_pct,
    }
    band_result = check_allocation_band(allocation_pct, target_pct, float(band))
    return {
        "available": True,
        "exchange": exchange_id,
        "source": "live",
        "nav_usd": round(float(snap.nav_usd), 2),
        "cash_usd": round(float(snap.cash_usd), 2),
        "allocation_pct": band_result["allocation_pct"],
        "target_allocation_pct": target_pct,
        "drift": band_result["drift"],
        "rebalance_hint": band_result["hint"],
        "outside_band": band_result["outside_band"],
        "prices": dict(snap.prices),
        "cash_breakdown": dict(snap.cash_breakdown),
        "snapshot_ts": snap.ts,
    }
