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
from alloccontext.ingest.quote_resolver import quote_resolver_config_from_app
from alloccontext.mcp.validation import validate_band, validate_target_pct
from alloccontext.rollup.allocation_analysis import build_allocation_analysis
from alloccontext.rollup.portfolio_payload import portfolio_dict_from_snapshot

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
    resolver_config = quote_resolver_config_from_app(config)
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
            return fetch_kraken_snapshot(client, spot, resolver_config=resolver_config)
        client = CoinbaseClient(
            api_key=key,
            api_secret=secret,
            retry_backoff=spot.retry_backoff_seconds,
            max_retries=spot.max_retries,
        )
        return fetch_coinbase_snapshot(client, spot, resolver_config=resolver_config)
    except (KrakenError, CoinbaseError) as exc:
        raise LivePortfolioError(str(exc)) from exc


def portfolio_state_from_snapshot(
    snap: PortfolioSnapshot,
    *,
    exchange_id: str,
    target_pct: dict[str, float] | None = None,
    band: float | None = None,
) -> dict[str, Any]:
    payload = portfolio_dict_from_snapshot(
        snap,
        exchange_id=exchange_id,
        source="live",
    )
    payload["snapshot_ts"] = snap.ts
    if target_pct is not None:
        payload["allocation_analysis"] = build_allocation_analysis(
            payload.get("allocation_pct") or {},
            validate_target_pct(target_pct),
            validate_band(band if band is not None else 0.15),
        )
    return payload
