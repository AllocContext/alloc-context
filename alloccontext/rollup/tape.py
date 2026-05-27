from __future__ import annotations

import datetime as dt
from typing import Any

from alloccontext.rollup.cf_math import (
    pct_change_over_minutes,
    range_pct_over_minutes,
    scale_pct_map,
    trend_pct_for_index,
)
from alloccontext.rollup.cluster import (
    MarketQuote,
    build_cluster_snapshot,
    cluster_advisory_fields,
    sentiment_up_fraction,
)
from alloccontext.rollup.cluster_config import RollupConfig


def _volatility_regime(
    range_pct: float | None,
    *,
    high_threshold: float,
    medium_threshold: float,
) -> str | None:
    if range_pct is None:
        return None
    if range_pct >= high_threshold:
        return "high"
    if range_pct >= medium_threshold:
        return "medium"
    return "low"


def _dominant_vol_regime(regimes: dict[str, str]) -> str | None:
    if not regimes:
        return None
    order = {"high": 3, "medium": 2, "low": 1}
    return max(regimes.values(), key=lambda value: order.get(value, 0))


def format_tape_summary(
    *,
    trend_60m: dict[str, float | None],
    vol_regime: str | None,
    sentiment_up_frac: float | None,
) -> str:
    scored = [(asset, pct) for asset, pct in trend_60m.items() if pct is not None]
    if not scored:
        direction = "mixed"
    else:
        down = sum(1 for _, pct in scored if pct < -0.05)
        up = sum(1 for _, pct in scored if pct > 0.05)
        if down >= max(3, len(scored) - 1):
            direction = "broad down"
        elif up >= max(3, len(scored) - 1):
            direction = "broad up"
        elif up > down:
            direction = "mixed, leaning up"
        elif down > up:
            direction = "mixed, leaning down"
        else:
            direction = "mixed"

    if vol_regime == "high":
        vol_label = "high short vol"
    elif vol_regime == "medium":
        vol_label = "elevated short vol"
    elif vol_regime == "low":
        vol_label = "calm short vol"
    else:
        vol_label = "short vol n/a"

    if sentiment_up_frac is None:
        sentiment_label = "hourly sentiment n/a"
    elif sentiment_up_frac >= 0.55:
        sentiment_label = "crowd leaning YES on hourly"
    elif sentiment_up_frac <= 0.45:
        sentiment_label = "crowd leaning NO on hourly"
    else:
        sentiment_label = "mixed hourly sentiment"

    return f"Tape today: {direction}, {vol_label}, {sentiment_label}."


def build_live_tape_context(
    config: RollupConfig,
    *,
    cf_history: dict[str, list[dict[str, Any]]] | None,
    markets: list[MarketQuote],
    now: dt.datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dt.datetime] | None:
    if not cf_history:
        return None

    now = now or dt.datetime.now(dt.timezone.utc)
    ctx = config.context_filter
    trend_cfg = config.trend_filter

    trend_60m: dict[str, float | None] = {}
    trend_15m: dict[str, float | None] = {}
    trend_5m: dict[str, float | None] = {}
    vol_by_asset: dict[str, str | None] = {}

    for asset_row in config.crypto:
        index = asset_row.cf_index
        if not index:
            continue
        trend_60m[asset_row.asset] = trend_pct_for_index(
            cf_history,
            index,
            now,
            lookback_minutes=trend_cfg.lookback_minutes,
            min_samples=trend_cfg.min_samples,
            enabled=trend_cfg.enabled,
        )
        trend_15m[asset_row.asset] = pct_change_over_minutes(
            cf_history,
            index,
            now,
            lookback_minutes=ctx.short_drift_15m_minutes,
            min_samples=ctx.min_samples_short,
        )
        trend_5m[asset_row.asset] = pct_change_over_minutes(
            cf_history,
            index,
            now,
            lookback_minutes=ctx.short_drift_5m_minutes,
            min_samples=ctx.min_samples_short,
        )
        range_pct = range_pct_over_minutes(
            cf_history,
            index,
            now,
            lookback_minutes=ctx.volatility_lookback_minutes,
            min_samples=ctx.min_samples_short,
        )
        vol_by_asset[asset_row.asset] = _volatility_regime(
            range_pct,
            high_threshold=ctx.high_volatility_pct,
            medium_threshold=ctx.medium_volatility_pct,
        )

    cluster = build_cluster_snapshot(
        config.cluster_log,
        crypto_assets=config.crypto,
        cf_history=cf_history,
        markets=markets,
        now=now,
        min_samples_short=ctx.min_samples_short,
    )
    dominant_vol = _dominant_vol_regime(
        {asset: regime for asset, regime in vol_by_asset.items() if regime}
    )
    sentiment_up_frac = cluster.sentiment_up_frac if cluster else None
    if sentiment_up_frac is None and markets:
        sentiment_up_frac, _ = sentiment_up_fraction(markets)

    tape_context = {
        "summary": format_tape_summary(
            trend_60m=scale_pct_map(trend_60m),
            vol_regime=dominant_vol,
            sentiment_up_frac=sentiment_up_frac,
        ),
        "trend_60m_pct": scale_pct_map(trend_60m),
        "trend_15m_pct": scale_pct_map(trend_15m),
        "trend_5m_pct": scale_pct_map(trend_5m),
        "volatility_regime": dominant_vol,
        "volatility_by_asset": {
            asset: regime for asset, regime in vol_by_asset.items() if regime
        }
        or None,
    }
    cluster_context = cluster_advisory_fields(cluster)
    return tape_context, cluster_context, now
