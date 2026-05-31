from __future__ import annotations

# Canonical allocation universe shared by rollup math and MCP handlers.
ALLOCATION_ASSETS: tuple[str, ...] = ("BTC", "ETH", "CASH")

# Assets with ingest-backed market and ETF context blocks.
MARKET_VIEW_ASSETS: tuple[str, ...] = ("BTC", "ETH")

# Assets surfaced in market/ETF views when a caller does not request a subset.
DEFAULT_VIEW_ASSETS: tuple[str, ...] = MARKET_VIEW_ASSETS
