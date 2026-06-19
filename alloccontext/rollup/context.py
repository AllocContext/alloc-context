from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Literal

from alloccontext.store.jsonutil import canonical_json

from alloccontext.rollup.cluster_config import RollupConfig, load_rollup_config
from alloccontext.ingest.alt_quote_registry import market_alt_symbols
from alloccontext.rollup.delta import build_delta_context
from alloccontext.rollup.macro import build_macro_context
from alloccontext.rollup.material_moves import build_portfolio_material_moves
from alloccontext.rollup.portfolio import build_market_context, build_portfolio_context
from alloccontext.rollup.regime import build_regime_context
from alloccontext.rollup.regime_history import attach_regime_history
from alloccontext.rollup.sentiment import build_sentiment_context

Scope = Literal["daily", "weekly"]


def _load_prior_context(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    prior_as_of: str | None,
) -> dict[str, Any] | None:
    if not prior_as_of:
        return None
    row = conn.execute(
        """
        SELECT context_json FROM context_snapshots
        WHERE scope = ? AND as_of = ?
        """,
        (scope, prior_as_of),
    ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row["context_json"])
    except (TypeError, json.JSONDecodeError):
        return None


def _save_context_snapshot(
    conn: sqlite3.Connection,
    *,
    scope: Scope,
    as_of: str,
    context: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        VALUES (?, ?, ?)
        ON CONFLICT(scope, as_of) DO UPDATE SET
          context_json = excluded.context_json
        """,
        (scope, as_of, canonical_json(context)),
    )
    conn.commit()


def build_context_bundle(
    conn,
    config,
    *,
    scope: Scope,
    rollup: RollupConfig,
    as_of: datetime | None = None,
    save_snapshot: bool = False,
    alt_symbols: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    now = (as_of or datetime.now(timezone.utc)).replace(microsecond=0)

    prior_row = conn.execute(
        """
        SELECT as_of FROM context_snapshots
        WHERE scope = ? AND as_of < ?
        ORDER BY as_of DESC LIMIT 1
        """,
        (scope, now.isoformat()),
    ).fetchone()
    prior_as_of = prior_row["as_of"] if prior_row else None
    prior_context = _load_prior_context(conn, scope=scope, prior_as_of=prior_as_of)

    portfolio = build_portfolio_context(conn, config)
    market = build_market_context(
        conn,
        config,
        alt_symbols=market_alt_symbols(conn, extra=alt_symbols),
    )
    sentiment = build_sentiment_context(conn, config, rollup, now=now)
    macro = build_macro_context(conn, config, now=now, scope=scope)
    delta = build_delta_context(
        conn,
        now=now,
        portfolio=portfolio,
        sentiment=sentiment,
        market=market,
        prior_context=prior_context,
    )
    material_moves = build_portfolio_material_moves(
        portfolio=portfolio,
        market=market,
        delta=delta,
    )
    if material_moves:
        portfolio = {**portfolio, "material_moves": material_moves}

    bundle = {
        "bundle_id": f"{scope}:{now.isoformat()}",
        "scope": scope,
        "as_of": now.isoformat(),
        "prior_as_of": prior_as_of,
        "horizon_days": config.horizon.days,
        "portfolio": portfolio,
        "market": market,
        "sentiment": sentiment,
        "macro": macro,
        "delta": delta,
        "regime": build_regime_context(
            portfolio=portfolio,
            sentiment=sentiment,
            delta=delta,
            market=market,
            prior_as_of=prior_as_of,
            conn=conn,
            config=config,
            now=now,
        ),
    }
    if save_snapshot:
        _save_context_snapshot(conn, scope=scope, as_of=bundle["as_of"], context=bundle)
    return attach_regime_history(conn, scope=scope, bundle=bundle)
