from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from alloccontext.ingest.exchange.kraken_adapter import refresh_kraken_exchange
from alloccontext.ingest.exchange.types import ExchangeId

ExchangeRefreshFn = Callable[[sqlite3.Connection, Any], dict[str, Any]]

_ADAPTERS: dict[ExchangeId, ExchangeRefreshFn] = {
    "kraken": refresh_kraken_exchange,
}


def refresh_exchange(
    conn: sqlite3.Connection,
    config,
    exchange_id: ExchangeId,
) -> dict[str, Any]:
    adapter = _ADAPTERS.get(exchange_id)
    if adapter is None:
        return {"ok": False, "rows": 0, "error": f"unknown_exchange:{exchange_id}"}
    return adapter(conn, config)
