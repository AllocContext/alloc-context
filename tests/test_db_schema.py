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
