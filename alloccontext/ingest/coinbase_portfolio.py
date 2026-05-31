from __future__ import annotations

import os
import sqlite3
from typing import Any

from alloccontext.ingest.coinbase_client import (
    CoinbaseClient,
    CoinbaseError,
    normalize_pem_secret,
    product_to_symbol,
)
from alloccontext.timeutil import utc_now_iso
from alloccontext.ingest.kraken_portfolio import (
    PortfolioSnapshot,
    portfolio_from_balances,
    upsert_market_bars,
    upsert_portfolio_snapshot,
)
from alloccontext.ingest.quote_resolver import (
    QuoteResolverConfig,
    quote_resolver_config_from_env,
    resolve_balance_prices,
)


def load_coinbase_credentials() -> tuple[str, str] | None:
    api_key = os.environ.get("COINBASE_API_KEY", "").strip()
    api_secret = normalize_pem_secret(os.environ.get("COINBASE_API_SECRET", ""))
    if api_key and api_secret:
        return api_key, api_secret
    return None


def build_coinbase_client(spot) -> CoinbaseClient:
    creds = load_coinbase_credentials()
    return CoinbaseClient(
        api_key=creds[0] if creds else "",
        api_secret=creds[1] if creds else "",
        retry_backoff=spot.retry_backoff_seconds,
        max_retries=spot.max_retries,
    )


def _coinbase_price_for_symbol(client: CoinbaseClient, symbol: str) -> float | None:
    try:
        return client.get_ticker(f"{symbol}-USD")["last"]
    except CoinbaseError:
        return None


def fetch_portfolio_snapshot(
    client: CoinbaseClient,
    spot,
    *,
    resolver_config: QuoteResolverConfig | None = None,
) -> PortfolioSnapshot:
    spot_prices: dict[str, float] = {}
    for product_id in spot.pairs:
        symbol = product_to_symbol(product_id)
        spot_prices[symbol] = client.get_ticker(product_id)["last"]
    balances, cash_breakdown = client.get_balances_with_breakdown()
    prices = resolve_balance_prices(
        balances,
        spot_prices,
        exchange_price=lambda symbol: _coinbase_price_for_symbol(client, symbol),
        resolver_config=resolver_config or quote_resolver_config_from_env(),
    )
    snap = portfolio_from_balances(balances, prices, cash_breakdown=cash_breakdown)
    snap.ts = utc_now_iso()
    return snap


def refresh_coinbase(conn: sqlite3.Connection, config) -> dict[str, Any]:
    from alloccontext.ingest.exchange.registry import refresh_exchange

    return refresh_exchange(conn, config, "coinbase")
