from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from alloccontext.store.db import SCHEMA_VERSION, connect


def _v7_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta VALUES ('version', '7');
        CREATE TABLE brief_archive (
          scope TEXT NOT NULL,
          as_of TEXT NOT NULL,
          context_json TEXT NOT NULL,
          body_markdown TEXT,
          delivered_via TEXT,
          PRIMARY KEY (scope, as_of)
        );
        INSERT INTO brief_archive(scope, as_of, context_json)
        VALUES ('daily', '2026-05-20T12:00:00+00:00', '{"portfolio":{"nav_usd":100}}');
        INSERT INTO brief_archive(scope, as_of, context_json)
        VALUES ('weekly', '2026-05-19T12:00:00+00:00', '{"portfolio":{"nav_usd":99}}');
        """
    )
    conn.commit()
    conn.close()


def test_schema_v7_copies_archived_rows_to_context_snapshots() -> None:
    db_path = Path(tempfile.mkdtemp()) / "v7.db"
    _v7_db(db_path)

    conn = connect(db_path)
    version = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'version'"
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT scope, as_of, context_json FROM context_snapshots ORDER BY scope"
    ).fetchall()

    assert int(version) == SCHEMA_VERSION
    assert len(rows) == 2
    assert rows[0]["scope"] == "daily"
    assert '"nav_usd":100' in rows[0]["context_json"]
    assert rows[1]["scope"] == "weekly"


def test_schema_v7_is_idempotent_on_conflict() -> None:
    db_path = Path(tempfile.mkdtemp()) / "v7.db"
    _v7_db(db_path)

    connect(db_path).close()
    conn = connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM context_snapshots").fetchone()[0]
    assert count == 2


def _v8_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta VALUES ('version', '8');
        CREATE TABLE context_snapshots (
          scope TEXT NOT NULL,
          as_of TEXT NOT NULL,
          context_json TEXT NOT NULL,
          PRIMARY KEY (scope, as_of)
        );
        """
    )
    conn.commit()
    conn.close()


def test_schema_v8_adds_alt_quote_tables() -> None:
    db_path = Path(tempfile.mkdtemp()) / "v8.db"
    _v8_db(db_path)

    conn = connect(db_path)
    version = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'version'"
    ).fetchone()[0]
    alt_snapshots = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'alt_quote_snapshots'"
    ).fetchone()
    alt_scope = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'alt_quote_scope'"
    ).fetchone()

    assert int(version) == SCHEMA_VERSION
    assert alt_snapshots is not None
    assert alt_scope is not None


def _v9_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta VALUES ('version', '9');
        CREATE TABLE alt_quote_snapshots (
          symbol TEXT NOT NULL,
          snapshot_ts TEXT NOT NULL,
          price_usd REAL NOT NULL,
          change_pct_24h REAL,
          source TEXT NOT NULL,
          fetched_at TEXT NOT NULL,
          PRIMARY KEY (symbol, snapshot_ts)
        );
        CREATE TABLE alt_quote_scope (
          symbol TEXT PRIMARY KEY,
          last_requested_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def test_schema_v9_adds_onchain_cycle_daily() -> None:
    db_path = Path(tempfile.mkdtemp()) / "v9.db"
    _v9_db(db_path)

    conn = connect(db_path)
    version = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'version'"
    ).fetchone()[0]
    cycle = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'onchain_cycle_daily'"
    ).fetchone()

    assert int(version) == SCHEMA_VERSION
    assert cycle is not None
