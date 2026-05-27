from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


def _asset_price(context: dict[str, Any] | None, symbol: str) -> float | None:
    if not context:
        return None
    market = context.get("market") or {}
    if not market.get("available"):
        return None
    assets = market.get("assets") or {}
    block = assets.get(symbol.lower()) or assets.get(symbol)
    if not isinstance(block, dict):
        return None
    price = block.get("price_usd")
    return float(price) if price is not None else None


def _pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return round((current - prior) / prior * 100, 2)


def build_delta_context(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    portfolio: dict[str, Any],
    sentiment: dict[str, Any],
    market: dict[str, Any],
    prior_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    delta: dict[str, Any] = {"available": True, "notable_shifts": []}

    fg = sentiment.get("fear_greed") if sentiment.get("available") else None
    if fg:
        prior_fg_value = None
        if prior_context:
            prior_sentiment = prior_context.get("sentiment") or {}
            prior_fg = prior_sentiment.get("fear_greed") or {}
            if prior_fg.get("value") is not None:
                prior_fg_value = int(prior_fg["value"])
        if prior_fg_value is None:
            from alloccontext.rollup.fear_greed import fear_greed_at_or_before

            day_ago = int((now - timedelta(days=1)).timestamp())
            prior_row = fear_greed_at_or_before(conn, at_ts=day_ago)
            if prior_row:
                prior_fg_value = int(prior_row["value"])

        if prior_fg_value is not None:
            change = int(fg["value"]) - prior_fg_value
            delta["fear_greed_change"] = change
            if abs(change) >= 5:
                delta["notable_shifts"].append(
                    f"F&G {prior_fg_value} → {fg['value']} ({change:+d})"
                )

    if portfolio.get("available"):
        nav = portfolio.get("nav_usd")
        prior_nav = None
        if prior_context:
            prior_portfolio = prior_context.get("portfolio") or {}
            if prior_portfolio.get("nav_usd") is not None:
                prior_nav = float(prior_portfolio["nav_usd"])
        if prior_nav is not None and nav is not None:
            pnl = round(float(nav) - prior_nav, 2)
            delta["portfolio_nav_change_usd"] = pnl
            if abs(pnl) >= 100:
                delta["notable_shifts"].append(
                    f"Portfolio Δ ${pnl:+.2f} since prior brief"
                )
        else:
            pnl = (portfolio.get("pnl_usd") or {}).get("since_prior_snapshot")
            if pnl is not None:
                delta["portfolio_nav_change_usd"] = pnl
                if abs(float(pnl)) >= 100:
                    delta["notable_shifts"].append(
                        f"Portfolio Δ ${pnl:+.2f} vs prior snapshot"
                    )

    market_changes: dict[str, float | None] = {}
    for symbol in ("btc", "eth"):
        current = _asset_price(market, symbol)
        prior = _asset_price(prior_context, symbol)
        change = _pct_change(current, prior)
        if change is not None:
            market_changes[f"{symbol}_change_pct_since_prior"] = change
            if abs(change) >= 2:
                delta["notable_shifts"].append(
                    f"{symbol.upper()} {change:+.2f}% since prior brief"
                )
    if market_changes:
        delta["market"] = market_changes

    if not delta.get("notable_shifts"):
        has_metrics = (
            delta.get("fear_greed_change") is not None
            or delta.get("portfolio_nav_change_usd") is not None
            or bool(market_changes)
        )
        if not has_metrics:
            delta["available"] = False

    return delta
