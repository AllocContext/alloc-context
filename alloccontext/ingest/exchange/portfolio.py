from __future__ import annotations

from alloccontext.ingest.exchange.types import ExchangeId


def writes_portfolio_snapshot(config, exchange_id: ExchangeId) -> bool:
    """Only the configured primary exchange may upsert portfolio_snapshots."""
    return config.exchanges.primary == exchange_id
