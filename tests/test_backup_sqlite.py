from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from deploy.backup_sqlite import (
    backup_database,
    prune_old_backups,
    run_backup,
    run_restore,
)


def _seed_db(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t VALUES (?)", (label,))
        conn.commit()


def test_backup_and_restore_roundtrip(tmp_path: Path) -> None:
    trading = tmp_path / "trading"
    core_state = trading / "alloc-context" / "state"
    op_state = trading / "alloc-context-operator" / "state"
    _seed_db(core_state / "alloccontext.db", "core")
    _seed_db(op_state / "operator.db", "op")

    out = run_backup(trading_root=trading, retention_days=30)
    manifest = json.loads((out / "manifest.json").read_text())
    assert len(manifest["files"]) == 2

    with sqlite3.connect(core_state / "alloccontext.db") as conn:
        conn.execute("UPDATE t SET v = ?", ("stale",))
        conn.commit()
    run_restore(backup_dir=out, trading_root=trading)

    with sqlite3.connect(core_state / "alloccontext.db") as conn:
        row = conn.execute("SELECT v FROM t").fetchone()
    assert row == ("core",)


def test_prune_old_backups(tmp_path: Path) -> None:
    root = tmp_path / "backups"
    old = root / "20200101T000000Z"
    new = root / "20990101T000000Z"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / "manifest.json").write_text("{}", encoding="utf-8")
    (new / "manifest.json").write_text("{}", encoding="utf-8")

    removed = prune_old_backups(root, retention_days=14)
    assert "20200101T000000Z" in removed
    assert not old.exists()
    assert new.exists()


def test_backup_database_refuses_empty(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    try:
        backup_database(empty, tmp_path / "out.db")
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_backup_timer_schedule() -> None:
    text = (
        Path(__file__).resolve().parent.parent
        / "deploy/systemd/alloc-context-backup.timer"
    ).read_text()
    assert "04:15:00" in text
    assert "Persistent=true" in text
