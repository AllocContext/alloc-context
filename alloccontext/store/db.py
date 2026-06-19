from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 10

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  rows_upserted INTEGER NOT NULL DEFAULT 0,
  error TEXT
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL UNIQUE,
  nav_usd REAL,
  cash_usd REAL,
  allocation_json TEXT,
  raw_json TEXT
);

CREATE TABLE IF NOT EXISTS market_bars (
  pair TEXT NOT NULL,
  interval_minutes INTEGER NOT NULL,
  bar_ts INTEGER NOT NULL,
  open REAL NOT NULL,
  high REAL NOT NULL,
  low REAL NOT NULL,
  close REAL NOT NULL,
  PRIMARY KEY (pair, interval_minutes, bar_ts)
);

CREATE TABLE IF NOT EXISTS fear_greed (
  ts TEXT PRIMARY KEY,
  value INTEGER NOT NULL,
  classification TEXT,
  fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kalshi_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  tape_summary TEXT,
  cluster_json TEXT,
  raw_json TEXT
);

CREATE TABLE IF NOT EXISTS context_snapshots (
  scope TEXT NOT NULL,
  as_of TEXT NOT NULL,
  context_json TEXT NOT NULL,
  PRIMARY KEY (scope, as_of)
);

CREATE INDEX IF NOT EXISTS idx_context_snapshots_scope_as_of
  ON context_snapshots(scope, as_of);

CREATE TABLE IF NOT EXISTS macro_events (
  event_id TEXT PRIMARY KEY,
  event_ts TEXT NOT NULL,
  country TEXT NOT NULL,
  name TEXT NOT NULL,
  impact TEXT NOT NULL,
  category TEXT,
  actual TEXT,
  estimate TEXT,
  previous TEXT,
  unit TEXT,
  source TEXT NOT NULL,
  raw_json TEXT,
  fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_macro_events_ts ON macro_events(event_ts);

CREATE TABLE IF NOT EXISTS etf_flow_days (
  asset TEXT NOT NULL,
  flow_date TEXT NOT NULL,
  net_flow_usd REAL,
  total_value_traded_usd REAL,
  total_net_assets_usd REAL,
  cum_net_inflow_usd REAL,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (asset, flow_date)
);

CREATE TABLE IF NOT EXISTS etf_ticker_flows (
  asset TEXT NOT NULL,
  ticker TEXT NOT NULL,
  flow_date TEXT NOT NULL,
  net_flow_usd REAL,
  net_assets_usd REAL,
  institute TEXT,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (asset, ticker, flow_date)
);

CREATE TABLE IF NOT EXISTS crypto_market_snapshots (
  source TEXT NOT NULL,
  snapshot_ts TEXT NOT NULL,
  total_market_cap_usd REAL,
  btc_dominance_pct REAL,
  eth_dominance_pct REAL,
  btc_rank INTEGER,
  eth_rank INTEGER,
  btc_price_usd REAL,
  eth_price_usd REAL,
  btc_market_cap_usd REAL,
  eth_market_cap_usd REAL,
  btc_change_pct_24h REAL,
  eth_change_pct_24h REAL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (source, snapshot_ts)
);

CREATE INDEX IF NOT EXISTS idx_crypto_market_snapshots_ts ON crypto_market_snapshots(snapshot_ts);

CREATE TABLE IF NOT EXISTS fred_observations (
  series_id TEXT NOT NULL,
  obs_date TEXT NOT NULL,
  value REAL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (series_id, obs_date)
);

CREATE INDEX IF NOT EXISTS idx_fred_observations_series_date
  ON fred_observations(series_id, obs_date);

CREATE TABLE IF NOT EXISTS alt_quote_snapshots (
  symbol TEXT NOT NULL,
  snapshot_ts TEXT NOT NULL,
  price_usd REAL NOT NULL,
  change_pct_24h REAL,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (symbol, snapshot_ts)
);

CREATE INDEX IF NOT EXISTS idx_alt_quote_snapshots_symbol_ts
  ON alt_quote_snapshots(symbol, snapshot_ts DESC);

CREATE TABLE IF NOT EXISTS alt_quote_scope (
  symbol TEXT PRIMARY KEY,
  last_requested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS onchain_cycle_daily (
  as_of_date TEXT PRIMARY KEY,
  supply_profit_pct REAL NOT NULL,
  supply_loss_pct REAL NOT NULL,
  supply_profit_btc REAL,
  supply_loss_btc REAL,
  btc_price_usd REAL,
  source TEXT NOT NULL,
  ingested_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_onchain_cycle_daily_date
  ON onchain_cycle_daily(as_of_date DESC);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    migrate(conn)
    return conn


def _migrate_brief_archive_to_context_snapshots(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'brief_archive'
        """
    ).fetchone()
    if row is None:
        return
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        SELECT scope, as_of, context_json
        FROM brief_archive
        WHERE context_json IS NOT NULL AND context_json != ''
        ON CONFLICT(scope, as_of) DO NOTHING
        """
    )


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'version'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES ('version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
    elif int(row["value"]) < SCHEMA_VERSION:
        if int(row["value"]) <= 7:
            _migrate_brief_archive_to_context_snapshots(conn)
        if int(row["value"]) < 9:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS alt_quote_snapshots (
                  symbol TEXT NOT NULL,
                  snapshot_ts TEXT NOT NULL,
                  price_usd REAL NOT NULL,
                  change_pct_24h REAL,
                  source TEXT NOT NULL,
                  fetched_at TEXT NOT NULL,
                  PRIMARY KEY (symbol, snapshot_ts)
                );
                CREATE INDEX IF NOT EXISTS idx_alt_quote_snapshots_symbol_ts
                  ON alt_quote_snapshots(symbol, snapshot_ts DESC);
                CREATE TABLE IF NOT EXISTS alt_quote_scope (
                  symbol TEXT PRIMARY KEY,
                  last_requested_at TEXT NOT NULL
                );
                """
            )
        if int(row["value"]) < 10:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS onchain_cycle_daily (
                  as_of_date TEXT PRIMARY KEY,
                  supply_profit_pct REAL NOT NULL,
                  supply_loss_pct REAL NOT NULL,
                  supply_profit_btc REAL,
                  supply_loss_btc REAL,
                  btc_price_usd REAL,
                  source TEXT NOT NULL,
                  ingested_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_onchain_cycle_daily_date
                  ON onchain_cycle_daily(as_of_date DESC);
                """
            )
        conn.execute(
            "UPDATE schema_meta SET value = ? WHERE key = 'version'",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
    elif int(row["value"]) > SCHEMA_VERSION:
        raise RuntimeError(
            f"database schema version {row['value']} is newer than "
            f"supported {SCHEMA_VERSION}; upgrade the application"
        )


def record_ingest_run(
    conn: sqlite3.Connection,
    *,
    source: str,
    started_at: str,
    finished_at: str,
    rows_upserted: int,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ingest_runs(source, started_at, finished_at, rows_upserted, error)
        VALUES (?, ?, ?, ?, ?)
        """,
        (source, started_at, finished_at, rows_upserted, error),
    )
    conn.commit()
