from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from alloccontext.ingest.wallet.chains import DEFAULT_WALLET_CHAIN_IDS
from alloccontext.rollup.cluster_config import RollupConfig, load_rollup_config


@dataclass(frozen=True)
class PathsConfig:
    db: Path


@dataclass(frozen=True)
class PortfolioConfig:
    target_allocations: dict[str, float]
    rebalance_band: float
    max_cash_risk_off: float  # deprecated ADR-020; ignored by core regime rollup
    notes: str


@dataclass(frozen=True)
class HorizonConfig:
    """Quarterly scope for stored history (default 90 days)."""

    days: int


_KALSHI_ALLOWED_HOSTS = frozenset(
    {
        "api.elections.kalshi.com",
        "trading-api.kalshi.com",
    }
)

_ONCHAIN_BITVIEW_HOSTS = frozenset({"bitview.space"})


def _validate_https_host_url(url: str, *, allowed_hosts: frozenset[str], label: str) -> str:
    normalized = url.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https":
        raise ValueError(f"{label} must use https, got {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if not host or host not in allowed_hosts:
        allowed = ", ".join(sorted(allowed_hosts))
        raise ValueError(f"{label} host {host!r} not allowed ({allowed})")
    if parsed.path not in ("", "/"):
        raise ValueError(f"{label} must not include a path")
    return normalized


def _validate_kalshi_base_url(url: str) -> str:
    normalized = url.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https":
        raise ValueError(f"kalshi.base_url must use https, got {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if host not in _KALSHI_ALLOWED_HOSTS:
        allowed = ", ".join(sorted(_KALSHI_ALLOWED_HOSTS))
        raise ValueError(f"kalshi.base_url host {host!r} not allowed ({allowed})")
    return normalized


DEFAULT_OPTIONAL_INGEST_SOURCES = frozenset(
    {
        "fred",
        "finnhub",
        "fmp",
        "coingecko",
        "coinmarketcap",
        "sosovalue",
        "onchain_cycle",
    }
)


@dataclass(frozen=True)
class IngestConfig:
    interval_minutes: int
    sources: dict[str, bool]
    optional_sources: frozenset[str]


@dataclass(frozen=True)
class KrakenConfig:
    ohlc_interval_minutes: int
    pairs: list[str]
    retry_backoff_seconds: float
    max_retries: int


@dataclass(frozen=True)
class SpotExchangeConfig:
    enabled: bool
    ohlc_interval_minutes: int
    pairs: list[str]
    retry_backoff_seconds: float
    max_retries: int


@dataclass(frozen=True)
class ExchangesConfig:
    primary: str
    kraken: SpotExchangeConfig
    coinbase: SpotExchangeConfig

    def primary_spot(self) -> SpotExchangeConfig:
        if self.primary == "kraken":
            return self.kraken
        if self.primary == "coinbase":
            return self.coinbase
        raise ValueError(f"unsupported primary exchange: {self.primary}")


@dataclass(frozen=True)
class WalletConfig:
    enabled: bool
    provider: str
    chain_ids: tuple[int, ...]
    min_value_usd: float
    timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float


@dataclass(frozen=True)
class KalshiSeriesConfig:
    asset: str
    series: str
    cf_index: str


@dataclass(frozen=True)
class KalshiConfig:
    use_api: bool
    base_url: str
    timeout_seconds: float
    cf_history_max_age_minutes: int
    series: list[KalshiSeriesConfig]
    fallback_tactical_snapshot: Path | None
    fallback_state: Path | None
    fallback_daily_archive: Path | None


@dataclass(frozen=True)
class MacroConfig:
    static_calendar: Path
    countries: list[str]
    min_impact: str
    fetch_past_days: int
    fetch_future_days: int
    finnhub_enabled: bool
    fmp_enabled: bool
    timeout_seconds: float


@dataclass(frozen=True)
class EtfConfig:
    assets: list[str]
    sosovalue_enabled: bool
    fallback_snapshot: Path | None
    timeout_seconds: float


@dataclass(frozen=True)
class CoingeckoConfig:
    coin_ids: list[str]
    use_demo_key: bool
    timeout_seconds: float


@dataclass(frozen=True)
class FredSeriesSpec:
    id: str
    label: str
    category: str


@dataclass(frozen=True)
class FredConfig:
    series: list[FredSeriesSpec]
    lookback_days: int
    timeout_seconds: float


@dataclass(frozen=True)
class CoinmarketcapConfig:
    symbols: list[str]
    timeout_seconds: float


@dataclass(frozen=True)
class OnchainCycleConfig:
    provider: str
    bitview_base_url: str
    brk_base_url: str | None
    brk_allowed_hosts: frozenset[str]
    backfill_days: int
    max_staleness_days: int
    timeout_seconds: float


@dataclass(frozen=True)
class RegimeCycleConfig:
    convergence_spread_pct: float
    capitulation_loss_floor_pct: float
    euphoria_profit_pct: float
    distribution_profit_pct: float
    distribution_profit_drop_pct: float
    recovery_loss_pct: float
    recovery_spread_widen_pct: float
    history_7d_min_days: int
    history_7d_max_days: int


@dataclass(frozen=True)
class OnchainConfig:
    cycle: OnchainCycleConfig


@dataclass(frozen=True)
class RegimeConfig:
    cycle: RegimeCycleConfig


@dataclass(frozen=True)
class AppConfig:
    paths: PathsConfig
    horizon: HorizonConfig
    portfolio: PortfolioConfig
    ingest: IngestConfig
    kraken: KrakenConfig
    exchanges: ExchangesConfig
    wallet: WalletConfig
    kalshi: KalshiConfig
    rollup: RollupConfig
    macro: MacroConfig
    etf: EtfConfig
    coingecko: CoingeckoConfig
    coinmarketcap: CoinmarketcapConfig
    fred: FredConfig
    onchain: OnchainConfig
    regime: RegimeConfig


def _path(value: str | None, fallback: str) -> Path:
    return Path(value or fallback)


def _optional_ingest_sources(raw: Any) -> frozenset[str]:
    if raw is None:
        return DEFAULT_OPTIONAL_INGEST_SOURCES
    if not isinstance(raw, (list, tuple)):
        return DEFAULT_OPTIONAL_INGEST_SOURCES
    return frozenset(str(item).strip() for item in raw if str(item).strip())


def _load_fred_series(catalog_path: Path) -> list[FredSeriesSpec]:
    if not catalog_path.exists():
        return []
    raw = yaml.safe_load(catalog_path.read_text()) or {}
    rows = raw.get("series") or []
    specs: list[FredSeriesSpec] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        series_id = str(row.get("id") or "").strip()
        if not series_id:
            continue
        specs.append(
            FredSeriesSpec(
                id=series_id,
                label=str(row.get("label") or series_id),
                category=str(row.get("category") or "macro"),
            )
        )
    return specs


def _spot_fields(
    raw: dict[str, Any],
    *,
    default_pairs: list[str],
) -> dict[str, Any]:
    return {
        "ohlc_interval_minutes": int(raw.get("ohlc_interval_minutes") or 1440),
        "pairs": [str(p) for p in (raw.get("pairs") or default_pairs)],
        "retry_backoff_seconds": float(raw.get("retry_backoff_seconds") or 2.0),
        "max_retries": int(raw.get("max_retries") or 3),
    }


def _kraken_config_from_spot(spot: SpotExchangeConfig) -> KrakenConfig:
    return KrakenConfig(
        ohlc_interval_minutes=spot.ohlc_interval_minutes,
        pairs=list(spot.pairs),
        retry_backoff_seconds=spot.retry_backoff_seconds,
        max_retries=spot.max_retries,
    )


def _load_wallet_config(raw: dict[str, Any]) -> WalletConfig:
    wallet_raw = raw.get("wallet") or {}
    chain_ids_raw = wallet_raw.get("chain_ids")
    if chain_ids_raw:
        chain_ids = tuple(int(chain_id) for chain_id in chain_ids_raw)
    else:
        chain_ids = DEFAULT_WALLET_CHAIN_IDS
    provider = str(wallet_raw.get("provider") or "alchemy").strip().lower()
    if provider not in {"alchemy", "etherscan"}:
        raise ValueError(f"unsupported wallet.provider: {provider}")
    return WalletConfig(
        enabled=bool(wallet_raw.get("enabled", True)),
        provider=provider,
        chain_ids=chain_ids,
        min_value_usd=float(wallet_raw.get("min_value_usd") or 1.0),
        timeout_seconds=float(wallet_raw.get("timeout_seconds") or 20.0),
        max_retries=int(wallet_raw.get("max_retries") or 3),
        retry_backoff_seconds=float(wallet_raw.get("retry_backoff_seconds") or 2.0),
    )


def _load_exchanges_config(
    raw: dict[str, Any],
    *,
    kraken_raw: dict[str, Any],
    ingest_sources: dict[str, bool],
) -> ExchangesConfig:
    exchanges_raw = raw.get("exchanges") or {}
    if exchanges_raw:
        kr_raw = exchanges_raw.get("kraken") or {}
        kr_enabled = bool(kr_raw.get("enabled", ingest_sources.get("kraken", True)))
        cb_raw = exchanges_raw.get("coinbase") or {}
        cb_enabled = bool(cb_raw.get("enabled", ingest_sources.get("coinbase", False)))
        primary = str(exchanges_raw.get("primary") or "kraken")
    else:
        kr_raw = kraken_raw
        kr_enabled = bool(ingest_sources.get("kraken", True))
        cb_raw = {}
        cb_enabled = bool(ingest_sources.get("coinbase", False))
        primary = "kraken"

    kraken = SpotExchangeConfig(
        enabled=kr_enabled,
        **_spot_fields(kr_raw, default_pairs=["XBTUSD", "ETHUSD"]),
    )
    coinbase = SpotExchangeConfig(
        enabled=cb_enabled,
        **_spot_fields(cb_raw, default_pairs=["BTC-USD", "ETH-USD"]),
    )
    return ExchangesConfig(primary=primary, kraken=kraken, coinbase=coinbase)


def _resolve_config_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)
    env_path = os.environ.get("ALLOC_CONTEXT_CONFIG", "").strip()
    if env_path:
        return Path(env_path)
    local = Path("config/config.yaml")
    if local.exists():
        return local
    return Path("config/config.example.yaml")


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = _resolve_config_path(path)
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text()) or {}

    paths_raw = raw.get("paths") or {}
    horizon_raw = raw.get("horizon") or {}
    portfolio_raw = raw.get("portfolio") or {}
    ingest_raw = raw.get("ingest") or {}
    kraken_raw = raw.get("kraken") or {}
    kalshi_raw = raw.get("kalshi") or {}
    macro_raw = raw.get("macro") or {}
    etf_raw = raw.get("etf") or {}
    coingecko_raw = raw.get("coingecko") or {}
    coinmarketcap_raw = raw.get("coinmarketcap") or {}
    fred_raw = raw.get("fred") or {}
    onchain_raw = raw.get("onchain") or {}
    regime_raw = raw.get("regime") or {}

    db_env = os.environ.get("ALLOC_CONTEXT_DB", "").strip()
    db = _path(db_env or None, str(paths_raw.get("db") or "state/alloccontext.db"))

    kalshi_fallback_tactical = kalshi_raw.get("fallback_tactical_snapshot")
    kalshi_fallback_state = kalshi_raw.get("fallback_state")
    kalshi_fallback_daily = kalshi_raw.get("fallback_daily_archive")
    etf_fallback = etf_raw.get("fallback_snapshot")

    ingest_sources = {
        str(k): bool(v)
        for k, v in (ingest_raw.get("sources") or {}).items()
    }
    exchanges = _load_exchanges_config(
        raw,
        kraken_raw=kraken_raw,
        ingest_sources=ingest_sources,
    )
    kraken = _kraken_config_from_spot(exchanges.kraken)
    wallet = _load_wallet_config(raw)

    return AppConfig(
        paths=PathsConfig(
            db=db,
        ),
        horizon=HorizonConfig(
            days=int(horizon_raw.get("days") or 90),
        ),
        portfolio=PortfolioConfig(
            target_allocations=dict(portfolio_raw.get("target_allocations") or {}),
            rebalance_band=float(portfolio_raw.get("rebalance_band") or 0.15),
            max_cash_risk_off=float(portfolio_raw.get("max_cash_risk_off") or 0.50),
            notes=str(portfolio_raw.get("notes") or "").strip(),
        ),
        ingest=IngestConfig(
            interval_minutes=int(ingest_raw.get("interval_minutes") or 60),
            sources=ingest_sources,
            optional_sources=_optional_ingest_sources(ingest_raw.get("optional_sources")),
        ),
        kraken=kraken,
        exchanges=exchanges,
        wallet=wallet,
        kalshi=KalshiConfig(
            use_api=bool(kalshi_raw.get("use_api", True)),
            base_url=_validate_kalshi_base_url(
                str(
                    kalshi_raw.get("base_url")
                    or "https://api.elections.kalshi.com/trade-api/v2"
                )
            ),
            timeout_seconds=float(kalshi_raw.get("timeout_seconds") or 20.0),
            cf_history_max_age_minutes=int(kalshi_raw.get("cf_history_max_age_minutes") or 90),
            series=[
                KalshiSeriesConfig(
                    asset=str(row.get("asset") or ""),
                    series=str(row.get("series") or ""),
                    cf_index=str(row.get("cf_index") or ""),
                )
                for row in (kalshi_raw.get("series") or [])
                if isinstance(row, dict) and row.get("series")
            ]
            or [
                KalshiSeriesConfig(asset="BTC", series="KXBTCD", cf_index="BRTI"),
                KalshiSeriesConfig(asset="ETH", series="KXETHD", cf_index="ETHUSD_RTI"),
            ],
            fallback_tactical_snapshot=(
                Path(kalshi_fallback_tactical) if kalshi_fallback_tactical else None
            ),
            fallback_state=(
                Path(kalshi_fallback_state) if kalshi_fallback_state else None
            ),
            fallback_daily_archive=(
                Path(kalshi_fallback_daily) if kalshi_fallback_daily else None
            ),
        ),
        rollup=load_rollup_config(raw),
        macro=MacroConfig(
            static_calendar=_path(
                str(macro_raw.get("static_calendar") or "config/macro-calendar.yaml"),
                "config/macro-calendar.yaml",
            ),
            countries=[str(c).upper() for c in (macro_raw.get("countries") or ["US"])],
            min_impact=str(macro_raw.get("min_impact") or "medium").lower(),
            fetch_past_days=int(macro_raw.get("fetch_past_days") or 7),
            fetch_future_days=int(macro_raw.get("fetch_future_days") or 28),
            finnhub_enabled=bool(macro_raw.get("finnhub_enabled", True)),
            fmp_enabled=bool(macro_raw.get("fmp_enabled", False)),
            timeout_seconds=float(macro_raw.get("timeout_seconds") or 20.0),
        ),
        etf=EtfConfig(
            assets=[str(a).upper() for a in (etf_raw.get("assets") or ["BTC", "ETH"])],
            sosovalue_enabled=bool(etf_raw.get("sosovalue_enabled", True)),
            fallback_snapshot=Path(etf_fallback) if etf_fallback else None,
            timeout_seconds=float(etf_raw.get("timeout_seconds") or 20.0),
        ),
        coingecko=CoingeckoConfig(
            coin_ids=[str(c) for c in (coingecko_raw.get("coin_ids") or ["bitcoin", "ethereum"])],
            use_demo_key=bool(coingecko_raw.get("use_demo_key", True)),
            timeout_seconds=float(coingecko_raw.get("timeout_seconds") or 20.0),
        ),
        coinmarketcap=CoinmarketcapConfig(
            symbols=[str(s).upper() for s in (coinmarketcap_raw.get("symbols") or ["BTC", "ETH"])],
            timeout_seconds=float(coinmarketcap_raw.get("timeout_seconds") or 20.0),
        ),
        fred=FredConfig(
            series=_load_fred_series(
                _path(
                    str(fred_raw.get("series_catalog") or "config/fred-series.yaml"),
                    "config/fred-series.yaml",
                )
            ),
            lookback_days=int(fred_raw.get("lookback_days") or 120),
            timeout_seconds=float(fred_raw.get("timeout_seconds") or 20.0),
        ),
        onchain=_load_onchain_config(onchain_raw),
        regime=_load_regime_config(regime_raw),
    )


def _load_onchain_config(raw: dict[str, Any]) -> OnchainConfig:
    cycle_raw = raw.get("cycle") or {}
    brk_base = cycle_raw.get("brk_base_url")
    provider = str(cycle_raw.get("provider") or "bitview").strip().lower()
    if provider not in {"bitview", "brk"}:
        raise ValueError(f"unsupported onchain.cycle.provider: {provider}")
    brk_allowed_hosts = frozenset(
        str(host).strip().lower()
        for host in (cycle_raw.get("brk_allowed_hosts") or [])
        if str(host).strip()
    )
    bitview_base_url = _validate_https_host_url(
        str(cycle_raw.get("bitview_base_url") or "https://bitview.space"),
        allowed_hosts=_ONCHAIN_BITVIEW_HOSTS,
        label="onchain.cycle.bitview_base_url",
    )
    brk_base_url: str | None = None
    if brk_base:
        if not brk_allowed_hosts:
            raise ValueError(
                "onchain.cycle.brk_allowed_hosts required when brk_base_url is set"
            )
        brk_base_url = _validate_https_host_url(
            str(brk_base),
            allowed_hosts=brk_allowed_hosts,
            label="onchain.cycle.brk_base_url",
        )
    if provider == "brk":
        if not brk_base_url:
            raise ValueError("onchain.cycle.brk_base_url required when provider=brk")
    return OnchainConfig(
        cycle=OnchainCycleConfig(
            provider=provider,
            bitview_base_url=bitview_base_url,
            brk_base_url=brk_base_url,
            brk_allowed_hosts=brk_allowed_hosts,
            backfill_days=int(cycle_raw.get("backfill_days") or 3650),
            max_staleness_days=int(cycle_raw.get("max_staleness_days") or 3),
            timeout_seconds=float(cycle_raw.get("timeout_seconds") or 30.0),
        ),
    )


def _load_regime_config(raw: dict[str, Any]) -> RegimeConfig:
    cycle_raw = raw.get("cycle") or {}
    return RegimeConfig(
        cycle=RegimeCycleConfig(
            convergence_spread_pct=float(cycle_raw.get("convergence_spread_pct") or 5),
            capitulation_loss_floor_pct=float(
                cycle_raw.get("capitulation_loss_floor_pct") or 40
            ),
            euphoria_profit_pct=float(cycle_raw.get("euphoria_profit_pct") or 90),
            distribution_profit_pct=float(
                cycle_raw.get("distribution_profit_pct") or 80
            ),
            distribution_profit_drop_pct=float(
                cycle_raw.get("distribution_profit_drop_pct") or 3
            ),
            recovery_loss_pct=float(cycle_raw.get("recovery_loss_pct") or 25),
            recovery_spread_widen_pct=float(
                cycle_raw.get("recovery_spread_widen_pct") or 2
            ),
            history_7d_min_days=int(cycle_raw.get("history_7d_min_days") or 7),
            history_7d_max_days=int(cycle_raw.get("history_7d_max_days") or 14),
        ),
    )
