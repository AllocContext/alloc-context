from __future__ import annotations

import sqlite3
from typing import Any

from alloccontext.horizon import horizon_days
from alloccontext.ingest.outcome import (
    ingest_errors_from_source,
    optional_feed_errors,
    summarize_ingest_outcome,
)
from alloccontext.ingest.coingecko import refresh_coingecko
from alloccontext.ingest.coinmarketcap import refresh_coinmarketcap
from alloccontext.ingest.etf_flows import refresh_etf_flows
from alloccontext.ingest.fred import refresh_fred
from alloccontext.ingest.fear_greed import refresh_fear_greed
from alloccontext.ingest.kalshi import refresh_kalshi
from alloccontext.ingest.coinbase_portfolio import refresh_coinbase
from alloccontext.ingest.kraken_portfolio import refresh_kraken
from alloccontext.ingest.macro_calendar import refresh_macro_calendar
from alloccontext.store.db import record_ingest_run
from alloccontext.store.retention import prune_to_horizon
from alloccontext.timeutil import utc_now_iso


def _run_source(
    conn: sqlite3.Connection,
    config,
    source: str,
) -> dict[str, Any]:
    started = utc_now_iso()
    if source == "fear_greed":
        result = refresh_fear_greed(conn, history_limit=horizon_days(config))
    elif source == "kraken":
        result = refresh_kraken(conn, config)
    elif source == "coinbase":
        result = refresh_coinbase(conn, config)
    elif source == "kalshi":
        result = refresh_kalshi(conn, config)
    elif source == "macro_calendar":
        result = refresh_macro_calendar(conn, config)
    elif source == "etf_flows":
        result = refresh_etf_flows(conn, config)
    elif source == "coingecko":
        result = refresh_coingecko(conn, config)
    elif source == "coinmarketcap":
        result = refresh_coinmarketcap(conn, config)
    elif source == "fred":
        result = refresh_fred(conn, config)
    else:
        result = {"ok": False, "rows": 0, "error": f"unknown_source:{source}"}

    finished = utc_now_iso()
    rows = int(result.get("rows") or 0)
    source_errors = ingest_errors_from_source(
        source,
        result,
        config.ingest.optional_sources,
    )
    parent_error = source_errors.get(source)
    record_ingest_run(
        conn,
        source=source,
        started_at=started,
        finished_at=finished,
        rows_upserted=rows,
        error=parent_error,
    )
    for feed_name, message in optional_feed_errors(
        result, config.ingest.optional_sources
    ).items():
        record_ingest_run(
            conn,
            source=feed_name,
            started_at=started,
            finished_at=finished,
            rows_upserted=0,
            error=message,
        )
    return result


def run_ingest(
    conn: sqlite3.Connection,
    config,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Pull enabled sources into SQLite."""
    counts: dict[str, int] = {}
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for source, enabled in config.ingest.sources.items():
        if not enabled:
            counts[source] = 0
            continue
        if dry_run:
            counts[source] = 0
            results[source] = {"ok": True, "dry_run": True}
            continue
        result = _run_source(conn, config, source)
        results[source] = result
        counts[source] = int(result.get("rows") or 0)
        errors.update(
            ingest_errors_from_source(
                source,
                result,
                config.ingest.optional_sources,
            )
        )

    if not dry_run:
        from alloccontext.ingest.alt_quotes import refresh_scheduled_alt_quotes

        alt_result = refresh_scheduled_alt_quotes(conn, config)
        results["alt_quotes"] = alt_result
        counts["alt_quotes"] = int(alt_result.get("rows") or 0)

    outcome = summarize_ingest_outcome(errors, config.ingest.optional_sources)
    pruned: dict[str, int] = {}
    snapshots: dict[str, str] = {}
    if not dry_run:
        pruned = prune_to_horizon(conn, config)
        if not outcome["fatal_errors"]:
            from alloccontext.rollup.context import Scope, build_context_bundle

            for scope in ("daily", "weekly"):
                scope_lit: Scope = scope  # type: ignore[assignment]
                bundle = build_context_bundle(
                    conn,
                    config,
                    scope=scope_lit,
                    rollup=config.rollup,
                    save_snapshot=True,
                )
                snapshots[scope] = bundle["as_of"]

    return {
        "counts": counts,
        "results": results,
        "errors": outcome["errors"],
        "fatal_errors": outcome["fatal_errors"],
        "optional_errors": outcome["optional_errors"],
        "pruned": pruned,
        "snapshots": snapshots,
        "dry_run": dry_run,
        "ok": outcome["ok"],
        "partial": outcome["partial"],
        "horizon_days": horizon_days(config),
    }
