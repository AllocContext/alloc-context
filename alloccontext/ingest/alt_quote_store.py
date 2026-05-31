from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from alloccontext.ingest.asset_registry import normalize_canonical_symbol
from alloccontext.timeutil import utc_now_iso


@dataclass(frozen=True)
class AltQuoteRow:
    symbol: str
    snapshot_ts: str
    price_usd: float
    change_pct_24h: float | None
    source: str
    fetched_at: str


def upsert_alt_quote_snapshot(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    snapshot_ts: str,
    price_usd: float,
    change_pct_24h: float | None,
    source: str,
) -> None:
    fetched_at = utc_now_iso()
    conn.execute(
        """
        INSERT INTO alt_quote_snapshots(
          symbol, snapshot_ts, price_usd, change_pct_24h, source, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, snapshot_ts) DO UPDATE SET
          price_usd = excluded.price_usd,
          change_pct_24h = excluded.change_pct_24h,
          source = excluded.source,
          fetched_at = excluded.fetched_at
        """,
        (
            normalize_canonical_symbol(symbol),
            snapshot_ts,
            float(price_usd),
            change_pct_24h,
            source,
            fetched_at,
        ),
    )


def latest_alt_quote(conn: sqlite3.Connection, symbol: str) -> AltQuoteRow | None:
    row = conn.execute(
        """
        SELECT symbol, snapshot_ts, price_usd, change_pct_24h, source, fetched_at
        FROM alt_quote_snapshots
        WHERE symbol = ?
        ORDER BY snapshot_ts DESC
        LIMIT 1
        """,
        (normalize_canonical_symbol(symbol),),
    ).fetchone()
    return _row_to_quote(row) if row else None


def latest_alt_quotes(
    conn: sqlite3.Connection,
    symbols: list[str] | None = None,
) -> dict[str, AltQuoteRow]:
    if symbols:
        out: dict[str, AltQuoteRow] = {}
        for raw in symbols:
            quote = latest_alt_quote(conn, raw)
            if quote is not None:
                out[quote.symbol] = quote
        return out

    rows = conn.execute(
        """
        SELECT a.symbol, a.snapshot_ts, a.price_usd, a.change_pct_24h, a.source, a.fetched_at
        FROM alt_quote_snapshots a
        INNER JOIN (
          SELECT symbol, MAX(snapshot_ts) AS snapshot_ts
          FROM alt_quote_snapshots
          GROUP BY symbol
        ) latest
          ON latest.symbol = a.symbol AND latest.snapshot_ts = a.snapshot_ts
        ORDER BY a.symbol
        """
    ).fetchall()
    return {row["symbol"]: _row_to_quote(row) for row in rows}


def has_alt_quote(conn: sqlite3.Connection, symbol: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM alt_quote_snapshots
        WHERE symbol = ?
        LIMIT 1
        """,
        (normalize_canonical_symbol(symbol),),
    ).fetchone()
    return row is not None


def register_quote_scope(conn: sqlite3.Connection, symbols: list[str]) -> None:
    ts = utc_now_iso()
    for raw in symbols:
        symbol = normalize_canonical_symbol(raw)
        if not symbol or symbol in {"USD", "CASH"}:
            continue
        conn.execute(
            """
            INSERT INTO alt_quote_scope(symbol, last_requested_at)
            VALUES (?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
              last_requested_at = excluded.last_requested_at
            """,
            (symbol, ts),
        )
    conn.commit()


def recent_scope_symbols(conn: sqlite3.Connection, *, limit: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT symbol FROM alt_quote_scope
        ORDER BY last_requested_at DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    return [str(row["symbol"]) for row in rows]


def _row_to_quote(row: Any) -> AltQuoteRow:
    change = row["change_pct_24h"]
    return AltQuoteRow(
        symbol=str(row["symbol"]),
        snapshot_ts=str(row["snapshot_ts"]),
        price_usd=float(row["price_usd"]),
        change_pct_24h=float(change) if change is not None else None,
        source=str(row["source"]),
        fetched_at=str(row["fetched_at"]),
    )
