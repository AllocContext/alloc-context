from __future__ import annotations

from pathlib import Path
from typing import Any

from alloccontext.config import AppConfig, load_config
from alloccontext.ingest.exchange.live import (
    LivePortfolioError,
    fetch_live_portfolio_snapshot,
)
from alloccontext.mcp.setup import portfolio_not_configured
from alloccontext.user_config import UserConfig


def default_bridge_app_config() -> AppConfig:
    example = (
        Path(__file__).resolve().parent.parent.parent / "config" / "config.example.yaml"
    )
    return load_config(example)


def fetch_user_portfolio(user: UserConfig, config: AppConfig) -> dict[str, Any]:
    creds = user.primary_exchange_credentials()
    if creds is None:
        return portfolio_not_configured()

    try:
        snap = fetch_live_portfolio_snapshot(
            creds.exchange_id,  # type: ignore[arg-type]
            creds.api_key,
            creds.api_secret,
            config,
        )
    except LivePortfolioError as exc:
        return {
            "available": False,
            "reason": "portfolio_fetch_failed",
            "message": str(exc),
        }

    total = float(snap.nav_usd or 0)
    return {
        "available": True,
        "source": "live",
        "exchange": creds.exchange_id,
        "as_of": snap.ts,
        "nav_usd": round(total, 2),
        "cash_usd": round(float(snap.cash_usd or 0), 2),
        "allocation_pct": {
            "BTC": round(float(snap.btc_pct), 4),
            "ETH": round(float(snap.eth_pct), 4),
            "CASH": round(float(snap.cash_pct), 4),
        },
        "prices": dict(snap.prices),
        "cash_breakdown": dict(snap.cash_breakdown or {}),
    }


def merge_portfolio_into_bundle(
    bundle: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    result = dict(bundle)
    result["portfolio"] = portfolio
    return result
