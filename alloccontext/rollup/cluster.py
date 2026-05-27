from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from alloccontext.rollup.cf_math import pct_change_over_minutes
from alloccontext.rollup.cluster_config import ClusterLogConfig, CryptoAssetConfig


@dataclass(frozen=True)
class MarketQuote:
    ticker: str
    yes_ask_cents: int | None
    no_ask_cents: int | None


@dataclass(frozen=True)
class ClusterSnapshot:
    assets_with_drift: int
    drift_5m_by_asset: dict[str, float]
    weighted_drift_5m: float | None
    btc_drift_5m: float | None
    eth_drift_5m: float | None
    sentiment_up_frac: float | None
    sentiment_sample_size: int


def _alt_weight(cfg: ClusterLogConfig, alt_count: int) -> float:
    if alt_count <= 0:
        return 0.0
    remainder = max(0.0, 1.0 - cfg.btc_weight - cfg.eth_weight)
    return remainder / alt_count


def sentiment_up_fraction(markets: list[MarketQuote]) -> tuple[float | None, int]:
    samples = 0
    up_votes = 0
    for market in markets:
        yes_ask = market.yes_ask_cents
        no_ask = market.no_ask_cents
        if yes_ask is None or no_ask is None:
            continue
        samples += 1
        if yes_ask >= no_ask:
            up_votes += 1
    if samples == 0:
        return None, 0
    return up_votes / samples, samples


def build_cluster_snapshot(
    cfg: ClusterLogConfig,
    *,
    crypto_assets: tuple[CryptoAssetConfig, ...],
    cf_history: dict[str, list[dict[str, Any]]] | None,
    markets: list[MarketQuote],
    now: dt.datetime,
    min_samples_short: int,
) -> ClusterSnapshot | None:
    if not cfg.enabled or not cf_history:
        return None

    drift_5m_by_asset: dict[str, float] = {}
    for asset_row in crypto_assets:
        index = asset_row.cf_index
        if not index:
            continue
        drift = pct_change_over_minutes(
            cf_history,
            index,
            now,
            lookback_minutes=cfg.drift_lookback_minutes,
            min_samples=min_samples_short,
        )
        if drift is not None:
            drift_5m_by_asset[asset_row.asset] = drift

    if not drift_5m_by_asset:
        return None

    alt_assets = [
        asset
        for asset in crypto_assets
        if asset.asset not in cfg.leader_assets and asset.asset in drift_5m_by_asset
    ]
    alt_weight = _alt_weight(cfg, len(alt_assets))
    weighted = 0.0
    weight_used = 0.0
    for asset_row in crypto_assets:
        drift = drift_5m_by_asset.get(asset_row.asset)
        if drift is None:
            continue
        if asset_row.asset == "BTC":
            weight = cfg.btc_weight
        elif asset_row.asset == "ETH":
            weight = cfg.eth_weight
        else:
            weight = alt_weight
        weighted += drift * weight
        weight_used += weight
    weighted_drift = weighted / weight_used if weight_used > 0 else None

    sentiment_up_frac, sentiment_n = sentiment_up_fraction(markets)

    return ClusterSnapshot(
        assets_with_drift=len(drift_5m_by_asset),
        drift_5m_by_asset=drift_5m_by_asset,
        weighted_drift_5m=weighted_drift,
        btc_drift_5m=drift_5m_by_asset.get("BTC"),
        eth_drift_5m=drift_5m_by_asset.get("ETH"),
        sentiment_up_frac=sentiment_up_frac,
        sentiment_sample_size=sentiment_n,
    )


def cluster_advisory_fields(cluster: ClusterSnapshot | None) -> dict[str, Any]:
    if cluster is None:
        return {}

    drifts = list(cluster.drift_5m_by_asset.values())
    breadth = sum(1 for drift in drifts if drift > 0) / len(drifts) if drifts else None
    leaders_agree = None
    if cluster.btc_drift_5m is not None and cluster.eth_drift_5m is not None:
        leaders_agree = (cluster.btc_drift_5m > 0) == (cluster.eth_drift_5m > 0)

    fields: dict[str, Any] = {
        "assets_with_drift": cluster.assets_with_drift,
        "sentiment_sample": cluster.sentiment_sample_size,
    }
    if cluster.sentiment_up_frac is not None:
        fields["sentiment_up_frac"] = round(cluster.sentiment_up_frac, 4)
    if cluster.weighted_drift_5m is not None:
        fields["weighted_drift_5m_pct"] = round(cluster.weighted_drift_5m * 100, 4)
    if cluster.btc_drift_5m is not None:
        fields["btc_drift_5m_pct"] = round(cluster.btc_drift_5m * 100, 4)
    if cluster.eth_drift_5m is not None:
        fields["eth_drift_5m_pct"] = round(cluster.eth_drift_5m * 100, 4)
    drift_scaled = {
        asset: round(value * 100, 4)
        for asset, value in cluster.drift_5m_by_asset.items()
    }
    if drift_scaled:
        fields["drift_5m_by_asset"] = drift_scaled
    if breadth is not None:
        fields["breadth_up_frac"] = round(breadth, 4)
    if leaders_agree is not None:
        fields["leaders_agree"] = leaders_agree
    return fields
