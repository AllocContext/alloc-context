from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any

from alloccontext.ingest.kraken_client import KrakenClient, pair_to_symbol
from alloccontext.ingest.portfolio_holdings import (
    band_allocation_pct,
    build_holdings,
)
from alloccontext.ingest.quote_resolver import (
    QuoteResolverConfig,
    quote_resolver_config_from_env,
    resolve_balance_prices,
)
from alloccontext.timeutil import utc_now_iso


@dataclass
class PortfolioSnapshot:
    ts: str
    nav_usd: float
    cash_usd: float
    btc_usd: float
    eth_usd: float
    btc_pct: float
    eth_pct: float
    cash_pct: float
    prices: dict[str, float]
    cash_breakdown: dict[str, float] = field(default_factory=dict)
    holdings: list[dict[str, Any]] = field(default_factory=list)
    unrecognized: list[str] = field(default_factory=list)


def load_kraken_credentials() -> tuple[str, str] | None:
    api_key = os.environ.get("KRAKEN_API_KEY", "").strip()
    api_secret = os.environ.get("KRAKEN_API_SECRET", "").strip()
    if api_key and api_secret:
        return api_key, api_secret
    return None


def build_kraken_client(spot) -> KrakenClient:
    creds = load_kraken_credentials()
    return KrakenClient(
        api_key=creds[0] if creds else "",
        api_secret=creds[1] if creds else "",
        retry_backoff=spot.retry_backoff_seconds,
        max_retries=spot.max_retries,
    )


def portfolio_from_balances(
    balances: dict[str, float],
    prices: dict[str, float],
    *,
    cash_breakdown: dict[str, float] | None = None,
) -> PortfolioSnapshot:
    holdings, unrecognized = build_holdings(
        balances,
        prices,
        cash_breakdown=cash_breakdown,
    )
    allocation_pct = band_allocation_pct(holdings)
    nav_usd = round(
        sum(row.get("value_usd") or 0 for row in holdings if row.get("value_usd") is not None),
        2,
    )
    cash_usd = round(float(balances.get("USD") or 0), 2)
    btc_usd = round(
        next(
            (row.get("value_usd") or 0 for row in holdings if row.get("symbol") == "BTC"),
            0.0,
        ),
        2,
    )
    eth_usd = round(
        next(
            (row.get("value_usd") or 0 for row in holdings if row.get("symbol") == "ETH"),
            0.0,
        ),
        2,
    )
    return PortfolioSnapshot(
        ts="",
        nav_usd=nav_usd,
        cash_usd=cash_usd,
        btc_usd=btc_usd,
        eth_usd=eth_usd,
        btc_pct=allocation_pct["BTC"],
        eth_pct=allocation_pct["ETH"],
        cash_pct=allocation_pct["CASH"],
        prices=dict(prices),
        cash_breakdown=dict(cash_breakdown or {}),
        holdings=holdings,
        unrecognized=unrecognized,
    )


def _kraken_price_for_symbol(client: KrakenClient, symbol: str) -> float | None:
    candidates = [f"{symbol}USD", f"X{symbol}ZUSD", f"XX{symbol[:1]}TZUSD"]
    if symbol == "BTC":
        candidates = ["XBTUSD", "XXBTZUSD", *candidates]
    for pair in candidates:
        try:
            return client.get_ticker(pair)["last"]
        except Exception:  # noqa: BLE001
            continue
    return None


def fetch_portfolio_snapshot(
    client: KrakenClient,
    spot,
    *,
    resolver_config: QuoteResolverConfig | None = None,
) -> PortfolioSnapshot:
    spot_prices: dict[str, float] = {}
    for pair in spot.pairs:
        symbol = pair_to_symbol(pair)
        spot_prices[symbol] = client.get_ticker(pair)["last"]
    balances, cash_breakdown = client.get_balances_with_breakdown()
    prices = resolve_balance_prices(
        balances,
        spot_prices,
        exchange_price=lambda symbol: _kraken_price_for_symbol(client, symbol),
        resolver_config=resolver_config or quote_resolver_config_from_env(),
    )
    snap = portfolio_from_balances(balances, prices, cash_breakdown=cash_breakdown)
    snap.ts = utc_now_iso()
    return snap


def upsert_portfolio_snapshot(conn: sqlite3.Connection, snap: PortfolioSnapshot) -> None:
    allocation = {
        "BTC": snap.btc_pct,
        "ETH": snap.eth_pct,
        "CASH": snap.cash_pct,
        "btc_usd": snap.btc_usd,
        "eth_usd": snap.eth_usd,
        "prices": snap.prices,
        "cash_breakdown": snap.cash_breakdown,
        "holdings": snap.holdings,
        "unrecognized": snap.unrecognized,
    }
    raw = {**asdict(snap), "allocation": allocation}
    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ts) DO UPDATE SET
          nav_usd=excluded.nav_usd,
          cash_usd=excluded.cash_usd,
          allocation_json=excluded.allocation_json,
          raw_json=excluded.raw_json
        """,
        (
            snap.ts,
            snap.nav_usd,
            snap.cash_usd,
            json.dumps(allocation, sort_keys=True),
            json.dumps(raw, sort_keys=True),
        ),
    )


def upsert_market_bars(
    conn: sqlite3.Connection,
    *,
    pair: str,
    interval_minutes: int,
    bars: list[dict[str, float]],
) -> int:
    count = 0
    for bar in bars:
        conn.execute(
            """
            INSERT INTO market_bars(
              pair, interval_minutes, bar_ts, open, high, low, close
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pair, interval_minutes, bar_ts) DO UPDATE SET
              open=excluded.open,
              high=excluded.high,
              low=excluded.low,
              close=excluded.close
            """,
            (
                pair,
                interval_minutes,
                int(bar["time"]),
                float(bar["open"]),
                float(bar["high"]),
                float(bar["low"]),
                float(bar["close"]),
            ),
        )
        count += 1
    return count


def refresh_kraken(conn: sqlite3.Connection, config) -> dict[str, Any]:
    from alloccontext.ingest.exchange.registry import refresh_exchange

    return refresh_exchange(conn, config, "kraken")
