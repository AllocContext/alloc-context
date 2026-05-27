from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CryptoAssetConfig:
    asset: str
    cf_index: str


@dataclass(frozen=True)
class TrendFilterConfig:
    enabled: bool
    lookback_minutes: float
    min_samples: int


@dataclass(frozen=True)
class ContextFilterConfig:
    min_samples_short: int
    short_drift_5m_minutes: float
    short_drift_15m_minutes: float
    volatility_lookback_minutes: float
    medium_volatility_pct: float
    high_volatility_pct: float


@dataclass(frozen=True)
class ClusterLogConfig:
    enabled: bool
    drift_lookback_minutes: float
    btc_weight: float
    eth_weight: float
    leader_assets: tuple[str, ...]


@dataclass(frozen=True)
class RollupConfig:
    crypto: tuple[CryptoAssetConfig, ...]
    trend_filter: TrendFilterConfig
    context_filter: ContextFilterConfig
    cluster_log: ClusterLogConfig


def load_rollup_config(raw: dict[str, Any]) -> RollupConfig:
    rollup = raw.get("rollup") or {}
    trend = rollup.get("trend_filter") or {}
    ctx = rollup.get("context_filter") or {}
    cluster = rollup.get("cluster") or {}
    crypto_rows = rollup.get("crypto") or [
        {"asset": "BTC", "cf_index": "BRTI"},
        {"asset": "ETH", "cf_index": "ETHUSD_RTI"},
    ]

    return RollupConfig(
        crypto=tuple(
            CryptoAssetConfig(asset=str(row["asset"]), cf_index=str(row["cf_index"]))
            for row in crypto_rows
        ),
        trend_filter=TrendFilterConfig(
            enabled=bool(trend.get("enabled", True)),
            lookback_minutes=float(trend.get("lookback_minutes", 60)),
            min_samples=int(trend.get("min_samples", 4)),
        ),
        context_filter=ContextFilterConfig(
            min_samples_short=int(ctx.get("min_samples_short", 2)),
            short_drift_5m_minutes=float(ctx.get("short_drift_5m_minutes", 60)),
            short_drift_15m_minutes=float(ctx.get("short_drift_15m_minutes", 60)),
            volatility_lookback_minutes=float(ctx.get("volatility_lookback_minutes", 60)),
            medium_volatility_pct=float(ctx.get("medium_volatility_pct", 0.15)) / 100.0
            if float(ctx.get("medium_volatility_pct", 0.15)) > 1
            else float(ctx.get("medium_volatility_pct", 0.15)),
            high_volatility_pct=float(ctx.get("high_volatility_pct", 0.25)) / 100.0
            if float(ctx.get("high_volatility_pct", 0.25)) > 1
            else float(ctx.get("high_volatility_pct", 0.25)),
        ),
        cluster_log=ClusterLogConfig(
            enabled=bool(cluster.get("enabled", True)),
            drift_lookback_minutes=float(cluster.get("drift_lookback_minutes", 60)),
            btc_weight=float(cluster.get("btc_weight", 0.45)),
            eth_weight=float(cluster.get("eth_weight", 0.30)),
            leader_assets=tuple(str(a) for a in cluster.get("leader_assets") or ["BTC", "ETH"]),
        ),
    )
