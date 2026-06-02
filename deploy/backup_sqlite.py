"""Online SQLite backups for AllocContext production state (stdlib only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_CORE_DBS = ("alloccontext.db",)
DEFAULT_OPERATOR_DBS = ("operator.db",)


def backup_database(src: Path, dest: Path) -> int:
    """Copy src to dest using SQLite online backup. Returns bytes written."""
    if not src.is_file():
        raise FileNotFoundError(src)
    if src.stat().st_size == 0:
        raise ValueError(f"refusing to backup empty database: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with sqlite3.connect(src) as src_conn, sqlite3.connect(dest) as dest_conn:
        src_conn.backup(dest_conn)
    return dest.stat().st_size


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prune_old_backups(backup_root: Path, retention_days: int) -> list[str]:
    """Remove backup directories older than retention_days. Returns removed names."""
    if retention_days < 1:
        return []
    cutoff = datetime.now(UTC).timestamp() - (retention_days * 86400)
    removed: list[str] = []
    for child in sorted(backup_root.iterdir()):
        if not child.is_dir():
            continue
        try:
            stamp = datetime.strptime(child.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError:
            continue
        if stamp.timestamp() < cutoff:
            for path in sorted(child.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            child.rmdir()
            removed.append(child.name)
    return removed


def run_backup(
    *,
    trading_root: Path,
    backup_root: Path | None = None,
    retention_days: int = 14,
    core_dbs: tuple[str, ...] = DEFAULT_CORE_DBS,
    operator_dbs: tuple[str, ...] = DEFAULT_OPERATOR_DBS,
) -> Path:
    """Create a timestamped backup directory and manifest. Returns backup dir."""
    backup_root = backup_root or (trading_root / "backups")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = backup_root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    pairs = [
        (trading_root / "alloc-context" / "state", core_dbs),
        (trading_root / "alloc-context-operator" / "state", operator_dbs),
    ]
    for state_dir, names in pairs:
        for name in names:
            src = state_dir / name
            if not src.is_file():
                print(f"skip missing {src}", file=sys.stderr)
                continue
            if src.stat().st_size == 0:
                print(f"skip empty {src}", file=sys.stderr)
                continue
            dest = out_dir / state_dir.parent.name / "state" / name
            size = backup_database(src, dest)
            entries.append(
                {
                    "role": state_dir.parent.name,
                    "name": name,
                    "source": str(src),
                    "backup": str(dest),
                    "bytes": size,
                    "sha256": sha256_file(dest),
                }
            )
            print(f"backed up {src} -> {dest} ({size} bytes)")

    if not entries:
        raise RuntimeError("no databases were backed up")

    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "hostname": os.uname().nodename,
        "trading_root": str(trading_root),
        "files": entries,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path}")

    removed = prune_old_backups(backup_root, retention_days)
    for name in removed:
        print(f"pruned old backup {name}")
    return out_dir


def restore_database(backup_file: Path, dest: Path) -> None:
    """Replace dest with backup_file (after optional safety copy by caller)."""
    if not backup_file.is_file():
        raise FileNotFoundError(backup_file)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".restore-tmp")
    if tmp.exists():
        tmp.unlink()
    backup_database(backup_file, tmp)
    if dest.exists():
        dest.unlink()
    tmp.rename(dest)


def run_restore(
    *,
    backup_dir: Path,
    trading_root: Path,
    manifest_path: Path | None = None,
) -> None:
    """Restore databases listed in manifest.json under backup_dir."""
    manifest_path = manifest_path or (backup_dir / "manifest.json")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in data["files"]:
        rel = Path(entry["role"]) / "state" / entry["name"]
        src = backup_dir / rel
        dest = trading_root / rel
        print(f"restore {src} -> {dest}")
        safety = dest.with_suffix(dest.suffix + ".pre-restore")
        if dest.exists() and dest.stat().st_size > 0:
            if safety.exists():
                safety.unlink()
            backup_database(dest, safety)
            print(f"  safety copy -> {safety}")
        restore_database(src, dest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AllocContext SQLite backup/restore")
    sub = parser.add_subparsers(dest="command", required=True)

    backup_p = sub.add_parser("backup", help="Create timestamped backups")
    backup_p.add_argument(
        "--trading-root",
        type=Path,
        default=Path(os.environ.get("TRADING_ROOT", "/opt/trading")),
    )
    backup_p.add_argument("--backup-root", type=Path, default=None)
    backup_p.add_argument(
        "--retention-days",
        type=int,
        default=int(os.environ.get("BACKUP_RETENTION_DAYS", "14")),
    )

    restore_p = sub.add_parser("restore", help="Restore from a backup directory")
    restore_p.add_argument("backup_dir", type=Path)
    restore_p.add_argument(
        "--trading-root",
        type=Path,
        default=Path(os.environ.get("TRADING_ROOT", "/opt/trading")),
    )

    args = parser.parse_args(argv)
    if args.command == "backup":
        run_backup(
            trading_root=args.trading_root,
            backup_root=args.backup_root,
            retention_days=args.retention_days,
        )
        return 0
    if args.command == "restore":
        run_restore(backup_dir=args.backup_dir, trading_root=args.trading_root)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
