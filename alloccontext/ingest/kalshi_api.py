from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from alloccontext.ingest.cf_benchmarks import CFBenchmarksPriceError, fetch_prices
from alloccontext.ingest.cf_history import load_cf_history, record_cf_price_samples, save_cf_history
from alloccontext.ingest.kalshi_client import KalshiClient, no_ask_cents_from_row, price_cents_from_row
from alloccontext.ingest.kalshi_state import tactical_to_storage
from alloccontext.rollup.cluster import MarketQuote, sentiment_up_fraction
from alloccontext.rollup.cluster_config import RollupConfig
from alloccontext.rollup.tape import build_live_tape_context, format_tape_summary
from alloccontext.store.meta import set_meta


def _series_tickers(config) -> list[str]:
    return [row.series for row in config.kalshi.series if row.series]


def _cf_indices(config) -> list[str]:
    seen: set[str] = set()
    indices: list[str] = []
    for row in config.kalshi.series:
        if row.cf_index and row.cf_index not in seen:
            seen.add(row.cf_index)
            indices.append(row.cf_index)
    return indices


def fetch_series_market_quotes(
    client: KalshiClient, series_tickers: list[str]
) -> list[MarketQuote]:
    quotes: list[MarketQuote] = []
    seen: set[str] = set()
    for series in series_tickers:
        payload = client.get_markets(status="open", limit=100, series_ticker=series)
        for row in payload.get("markets") or []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "")
            if not ticker or ticker in seen:
                continue
            if not ticker.upper().startswith(series.upper()):
                continue
            yes_bid, yes_ask = price_cents_from_row(row)
            no_ask = no_ask_cents_from_row(row)
            if yes_ask is None and no_ask is None:
                continue
            quotes.append(
                MarketQuote(
                    ticker=ticker,
                    yes_ask_cents=yes_ask if yes_ask is not None else yes_bid,
                    no_ask_cents=no_ask,
                )
            )
            seen.add(ticker)
    return quotes


def _markets_meta_rows(markets: list[MarketQuote]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": market.ticker,
            "yes_ask_cents": market.yes_ask_cents,
            "no_ask_cents": market.no_ask_cents,
        }
        for market in markets
    ]


def build_api_tactical_payload(
    rollup: RollupConfig,
    *,
    cf_history: dict[str, list[dict[str, Any]]],
    markets: list[MarketQuote],
    now: datetime,
) -> dict[str, Any]:
    computed = build_live_tape_context(
        rollup,
        cf_history=cf_history or None,
        markets=markets,
        now=now,
    )
    if computed is not None:
        tape_ctx, cluster_ctx, at = computed
        return {
            "at": at.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            "tape_summary": tape_ctx.get("summary"),
            "trend_by_asset_60m": tape_ctx.get("trend_60m_pct") or {},
            "trend_by_asset_15m": tape_ctx.get("trend_15m_pct") or {},
            "volatility_regime": tape_ctx.get("volatility_regime"),
            "cluster": cluster_ctx,
            "daily_stats": {},
            "source": "kalshi_api",
        }

    sentiment_up_frac, sentiment_sample = sentiment_up_fraction(markets)
    cluster: dict[str, Any] = {}
    if sentiment_sample:
        cluster["sentiment_sample"] = sentiment_sample
    if sentiment_up_frac is not None:
        cluster["sentiment_up_frac"] = round(sentiment_up_frac, 4)

    return {
        "at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        "tape_summary": format_tape_summary(
            trend_60m={},
            vol_regime=None,
            sentiment_up_frac=sentiment_up_frac,
        ),
        "trend_by_asset_60m": {},
        "trend_by_asset_15m": {},
        "volatility_regime": None,
        "cluster": cluster,
        "daily_stats": {},
        "source": "kalshi_api",
    }


def refresh_kalshi_api(conn: sqlite3.Connection, config) -> dict[str, Any]:
    kalshi = config.kalshi
    series = _series_tickers(config)
    if not series:
        return {"ok": False, "error": "no_kalshi_series_configured", "rows": 0}

    now = datetime.now(timezone.utc)
    client = KalshiClient(kalshi.base_url, timeout=kalshi.timeout_seconds)

    try:
        markets = fetch_series_market_quotes(client, series)
    except Exception as exc:  # noqa: BLE001 — surface API errors to ingest runner
        return {"ok": False, "error": str(exc), "rows": 0}

    cf_history = load_cf_history(conn)
    indices = _cf_indices(config)
    cf_errors: dict[str, str] = {}
    if indices:
        try:
            prices = fetch_prices(indices, timeout=kalshi.timeout_seconds)
            cf_history = record_cf_price_samples(
                cf_history,
                prices,
                now,
                max_age_minutes=float(kalshi.cf_history_max_age_minutes),
            )
            save_cf_history(conn, cf_history)
        except CFBenchmarksPriceError as exc:
            cf_errors["cf_benchmarks"] = str(exc)

    if markets:
        set_meta(conn, "kalshi_markets", json.dumps(_markets_meta_rows(markets)))

    payload = build_api_tactical_payload(
        config.rollup,
        cf_history=cf_history,
        markets=markets,
        now=now,
    )
    if not markets and not cf_history:
        return {
            "ok": False,
            "error": "no_kalshi_markets_or_cf_history",
            "rows": 0,
            "feed_errors": cf_errors,
        }

    from alloccontext.ingest.kalshi_files import KalshiTacticalSnapshot

    snapshot = KalshiTacticalSnapshot(
        at=payload.get("at"),
        tape_summary=payload.get("tape_summary"),
        trend_by_asset_60m=dict(payload.get("trend_by_asset_60m") or {}),
        trend_by_asset_15m=dict(payload.get("trend_by_asset_15m") or {}),
        volatility_regime=payload.get("volatility_regime"),
        sentiment_up_frac=(payload.get("cluster") or {}).get("sentiment_up_frac"),
        sentiment_sample=(payload.get("cluster") or {}).get("sentiment_sample"),
        daily_stats=dict(payload.get("daily_stats") or {}),
    )
    storage = tactical_to_storage(snapshot, payload)

    from alloccontext.ingest.kalshi import upsert_kalshi_snapshot

    upsert_kalshi_snapshot(conn, storage)

    result: dict[str, Any] = {
        "ok": True,
        "rows": 1,
        "ts": storage["ts"],
        "tape_summary": storage.get("tape_summary"),
        "markets_sampled": len(markets),
        "source": "kalshi_api",
    }
    if cf_errors:
        result["feed_errors"] = cf_errors
    return result
