from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from alloccontext.rollup.cluster_config import RollupConfig, load_rollup_config


@dataclass(frozen=True)
class PathsConfig:
    db: Path
    brief_archive_dir: Path


@dataclass(frozen=True)
class CalendarConfig:
    timezone: str
    daily_brief_hour_local: int
    daily_brief_minute_local: int
    weekly_brief_day: str
    weekly_brief_hour_local: int
    weekly_brief_minute_local: int


@dataclass(frozen=True)
class PortfolioConfig:
    target_allocations: dict[str, float]
    rebalance_band: float
    max_cash_risk_off: float
    notes: str


@dataclass(frozen=True)
class HorizonConfig:
    """Quarterly scope for stored history (default 90 days)."""

    days: int


@dataclass(frozen=True)
class IngestConfig:
    interval_minutes: int
    sources: dict[str, bool]


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

    def primary_spot(self) -> SpotExchangeConfig:
        if self.primary == "kraken":
            return self.kraken
        raise ValueError(f"unsupported primary exchange: {self.primary}")


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
class SynthesisConfig:
    enabled: bool
    provider: str
    model: str
    temperature: float
    timeout_seconds: float
    daily_prompt_version: str
    weekly_prompt_version: str


@dataclass(frozen=True)
class EmailConfig:
    enabled: bool
    from_address: str | None
    to_address: str | None


@dataclass(frozen=True)
class AlertTriggersConfig:
    rebalance_band: bool


@dataclass(frozen=True)
class AlertsConfig:
    enabled: bool
    min_hours_between: int
    max_per_7d: int
    dedupe_hours: int
    triggers: AlertTriggersConfig


@dataclass(frozen=True)
class DeliverConfig:
    email: EmailConfig
    alerts: AlertsConfig


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
class AppConfig:
    paths: PathsConfig
    horizon: HorizonConfig
    calendar: CalendarConfig
    portfolio: PortfolioConfig
    ingest: IngestConfig
    kraken: KrakenConfig
    exchanges: ExchangesConfig
    kalshi: KalshiConfig
    rollup: RollupConfig
    synthesis: SynthesisConfig
    deliver: DeliverConfig
    macro: MacroConfig
    etf: EtfConfig
    coingecko: CoingeckoConfig
    coinmarketcap: CoinmarketcapConfig
    fred: FredConfig


def _path(value: str | None, fallback: str) -> Path:
    return Path(value or fallback)


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


def _spot_fields(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "ohlc_interval_minutes": int(raw.get("ohlc_interval_minutes") or 1440),
        "pairs": [str(p) for p in (raw.get("pairs") or ["XBTUSD", "ETHUSD"])],
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


def _load_exchanges_config(
    raw: dict[str, Any],
    *,
    kraken_raw: dict[str, Any],
    ingest_sources: dict[str, bool],
) -> ExchangesConfig:
    exchanges_raw = raw.get("exchanges") or {}
    if exchanges_raw:
        kr_raw = exchanges_raw.get("kraken") or {}
        enabled = bool(kr_raw.get("enabled", ingest_sources.get("kraken", True)))
        primary = str(exchanges_raw.get("primary") or "kraken")
    else:
        kr_raw = kraken_raw
        enabled = bool(ingest_sources.get("kraken", True))
        primary = "kraken"

    spot = SpotExchangeConfig(
        enabled=enabled,
        **_spot_fields(kr_raw),
    )
    return ExchangesConfig(primary=primary, kraken=spot)


def _resolve_config_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)
    env_path = os.environ.get("ALLOC_CONTEXT_CONFIG") or os.environ.get(
        "MARKET_ANALYST_CONFIG"
    )
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
    calendar_raw = raw.get("calendar") or {}
    portfolio_raw = raw.get("portfolio") or {}
    ingest_raw = raw.get("ingest") or {}
    kraken_raw = raw.get("kraken") or {}
    kalshi_raw = raw.get("kalshi") or {}
    synthesis_raw = raw.get("synthesis") or {}
    deliver_raw = raw.get("deliver") or {}
    email_raw = deliver_raw.get("email") or {}
    alerts_raw = deliver_raw.get("alerts") or {}
    macro_raw = raw.get("macro") or {}
    etf_raw = raw.get("etf") or {}
    coingecko_raw = raw.get("coingecko") or {}
    coinmarketcap_raw = raw.get("coinmarketcap") or {}
    fred_raw = raw.get("fred") or {}

    db_env = os.environ.get("ALLOC_CONTEXT_DB") or os.environ.get("MARKET_ANALYST_DB")
    db = _path(db_env, str(paths_raw.get("db") or "state/alloccontext.db"))

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

    return AppConfig(
        paths=PathsConfig(
            db=db,
            brief_archive_dir=_path(
                str(paths_raw.get("brief_archive_dir") or "state/briefs"),
                "state/briefs",
            ),
        ),
        horizon=HorizonConfig(
            days=int(horizon_raw.get("days") or 90),
        ),
        calendar=CalendarConfig(
            timezone=str(calendar_raw.get("timezone") or "America/Chicago"),
            daily_brief_hour_local=int(calendar_raw.get("daily_brief_hour_local") or 7),
            daily_brief_minute_local=int(calendar_raw.get("daily_brief_minute_local") or 0),
            weekly_brief_day=str(calendar_raw.get("weekly_brief_day") or "monday"),
            weekly_brief_hour_local=int(calendar_raw.get("weekly_brief_hour_local") or 7),
            weekly_brief_minute_local=int(calendar_raw.get("weekly_brief_minute_local") or 0),
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
        ),
        kraken=kraken,
        exchanges=exchanges,
        kalshi=KalshiConfig(
            use_api=bool(kalshi_raw.get("use_api", True)),
            base_url=str(
                kalshi_raw.get("base_url") or "https://api.elections.kalshi.com/trade-api/v2"
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
        synthesis=SynthesisConfig(
            enabled=bool(synthesis_raw.get("enabled", True)),
            provider=str(synthesis_raw.get("provider") or "openai"),
            model=str(synthesis_raw.get("model") or "gpt-4.1-mini"),
            temperature=float(synthesis_raw.get("temperature") or 0.3),
            timeout_seconds=float(synthesis_raw.get("timeout_seconds") or 60),
            daily_prompt_version=str(synthesis_raw.get("daily_prompt_version") or "daily_brief_v1"),
            weekly_prompt_version=str(
                synthesis_raw.get("weekly_prompt_version") or "weekly_brief_v1"
            ),
        ),
        deliver=DeliverConfig(
            email=EmailConfig(
                enabled=bool(email_raw.get("enabled", True)),
                from_address=email_raw.get("from_address"),
                to_address=email_raw.get("to_address"),
            ),
            alerts=AlertsConfig(
                enabled=bool(alerts_raw.get("enabled", False)),
                min_hours_between=int(alerts_raw.get("min_hours_between") or 24),
                max_per_7d=int(alerts_raw.get("max_per_7d") or 5),
                dedupe_hours=int(alerts_raw.get("dedupe_hours") or 72),
                triggers=AlertTriggersConfig(
                    rebalance_band=bool(
                        (alerts_raw.get("triggers") or {}).get("rebalance_band", True)
                    ),
                ),
            ),
        ),
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
    )
