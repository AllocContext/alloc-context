#!/usr/bin/env python3
"""Patch brief timer OnCalendar lines from alloc-context config YAML."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

TIMER_SPECS: dict[str, tuple[str, str]] = {
    "deploy/systemd/alloc-context-daily-brief.timer": (
        "daily_brief_hour_local",
        "daily_brief_minute_local",
    ),
    "deploy/systemd/alloc-context-weekly-brief.timer": (
        "weekly_brief_hour_local",
        "weekly_brief_minute_local",
    ),
}

ON_CALENDAR_RE = re.compile(r"^OnCalendar=.*$", re.MULTILINE)


def on_calendar(*, day_of_week: str | None, hour: int, minute: int, timezone: str) -> str:
    if day_of_week:
        return f"{day_of_week.capitalize()} *-*-* {hour:02d}:{minute:02d}:00 {timezone}"
    return f"*-*-* {hour:02d}:{minute:02d}:00 {timezone}"


def render_timer(path: Path, line: str) -> None:
    text = path.read_text()
    if not ON_CALENDAR_RE.search(text):
        raise SystemExit(f"No OnCalendar line in {path}")
    path.write_text(ON_CALENDAR_RE.sub(f"OnCalendar={line}", text, count=1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render alloc-context brief timers")
    parser.add_argument("--config", required=True)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    raw = yaml.safe_load(Path(args.config).read_text()) or {}
    calendar = raw.get("calendar") or {}
    tz = str(calendar.get("timezone") or "America/Chicago")

    daily = on_calendar(
        day_of_week=None,
        hour=int(calendar.get("daily_brief_hour_local") or 7),
        minute=int(calendar.get("daily_brief_minute_local") or 0),
        timezone=tz,
    )
    weekly = on_calendar(
        day_of_week=str(calendar.get("weekly_brief_day") or "monday"),
        hour=int(calendar.get("weekly_brief_hour_local") or 7),
        minute=int(calendar.get("weekly_brief_minute_local") or 0),
        timezone=tz,
    )

    mapping = {
        "deploy/systemd/alloc-context-daily-brief.timer": daily,
        "deploy/systemd/alloc-context-weekly-brief.timer": weekly,
    }
    for rel, line in mapping.items():
        path = args.repo_root / rel
        render_timer(path, line)
        print(f"updated {path.name}: OnCalendar={line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
