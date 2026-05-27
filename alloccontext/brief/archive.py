from __future__ import annotations

from datetime import datetime
from pathlib import Path


def brief_archive_path(archive_dir: Path, *, scope: str, as_of_iso: str) -> Path:
    dt = datetime.fromisoformat(as_of_iso)
    if scope == "daily":
        return archive_dir / "daily" / f"{dt.date()}.md"
    iso = dt.date().isocalendar()
    return archive_dir / "weekly" / f"{iso.year}-W{iso.week:02d}.md"


def write_brief_archive(
    archive_dir: Path,
    *,
    scope: str,
    as_of_iso: str,
    bundle_id: str,
    body: str,
) -> Path:
    path = brief_archive_path(archive_dir, scope=scope, as_of_iso=as_of_iso)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"---\n"
        f"scope: {scope}\n"
        f"as_of: {as_of_iso}\n"
        f"bundle_id: {bundle_id}\n"
        f"---\n\n"
    )
    path.write_text(header + body.strip() + "\n", encoding="utf-8")
    return path
