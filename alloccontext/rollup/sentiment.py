from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from alloccontext.rollup.cluster import MarketQuote
from alloccontext.rollup.cluster_config import RollupConfig
from alloccontext.rollup.tape import build_live_tape_context
from alloccontext.store.meta import get_meta


def _latest_snapshot(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT ts, tape_summary, cluster_json, raw_json
        FROM kalshi_snapshots ORDER BY id DESC LIMIT 1
        """
    ).fetchone()


def _markets_from_meta(conn: sqlite3.Connection) -> list[MarketQuote]:
    raw = get_meta(conn, "kalshi_markets") or get_meta(conn, "kalshi_markets_15m")
    if not raw:
        return []
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return []
    markets: list[MarketQuote] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        markets.append(
            MarketQuote(
                ticker=str(row.get("ticker") or ""),
                yes_ask_cents=row.get("yes_ask_cents"),
                no_ask_cents=row.get("no_ask_cents"),
            )
        )
    return markets


def _cf_history_from_meta(conn: sqlite3.Connection) -> dict[str, Any] | None:
    raw = get_meta(conn, "cf_price_history")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def build_kalshi_sentiment_context(
    conn: sqlite3.Connection,
    rollup: RollupConfig,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    row = _latest_snapshot(conn)
    if row is None:
        return {"available": False, "reason": "no_kalshi_snapshot"}

    cluster = json.loads(row["cluster_json"] or "{}")
    tape_summary = row["tape_summary"]
    source = "kalshi_snapshot"

    if not cluster:
        cf_history = _cf_history_from_meta(conn)
        markets = _markets_from_meta(conn)
        computed = build_live_tape_context(
            rollup,
            cf_history=cf_history,
            markets=markets,
            now=now,
        )
        if computed:
            tape_ctx, cluster_ctx, _computed_at = computed
            cluster = cluster_ctx
            tape_summary = tape_ctx.get("summary") or tape_summary
            source = "computed_cf_meta"

    if not cluster and not tape_summary:
        return {"available": False, "reason": "empty_kalshi_telemetry"}

    return {
        "available": True,
        "source": source,
        "as_of": row["ts"],
        "tape_summary": tape_summary,
        **cluster,
    }


def build_sentiment_context(
    conn: sqlite3.Connection,
    config,
    rollup: RollupConfig,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    from alloccontext.rollup.fear_greed import build_fear_greed_context

    now = now or datetime.now(timezone.utc)
    fg = build_fear_greed_context(conn, now=now)
    kalshi = build_kalshi_sentiment_context(conn, rollup, now=now)
    available = fg is not None or kalshi.get("available")
    body: dict[str, Any] = {
        "available": available,
        "fear_greed": fg,
        "kalshi": kalshi,
    }
    if not available:
        body["reason"] = "no_sentiment_sources"
    return body
