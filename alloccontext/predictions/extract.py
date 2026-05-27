from __future__ import annotations

import re
from dataclasses import dataclass

_FORWARD_SECTION = re.compile(
    r"^##\s+Forward watches\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_LEGACY_BULLET = re.compile(
    r"^-\s*IF\s+(.+?)\s*\|\s*WATCH\s+(.+?)(?:\s*\|\s*BY\s+(.+))?\s*$",
    re.IGNORECASE,
)
_NATURAL_BULLET = re.compile(
    r"^-\s*(?:If|When)\s+(.+?),\s*watch\s+(?:for\s+)?(.+?)"
    r"(?:\s+(?:by|before|through|until)\s+(.+?))?[.]?\s*$",
    re.IGNORECASE,
)
_ANY_BULLET = re.compile(r"^-\s+(.+)$")


@dataclass(frozen=True)
class ForwardWatch:
    condition_text: str
    watch_text: str
    by_text: str | None


def _parse_bullet(line: str) -> ForwardWatch | None:
    stripped = line.strip()
    legacy = _LEGACY_BULLET.match(stripped)
    if legacy:
        return ForwardWatch(
            condition_text=legacy.group(1).strip(),
            watch_text=legacy.group(2).strip(),
            by_text=(legacy.group(3).strip() if legacy.group(3) else None),
        )

    natural = _NATURAL_BULLET.match(stripped)
    if natural:
        return ForwardWatch(
            condition_text=natural.group(1).strip(),
            watch_text=natural.group(2).strip().rstrip("."),
            by_text=(natural.group(3).strip().rstrip(".") if natural.group(3) else None),
        )

    fallback = _ANY_BULLET.match(stripped)
    if fallback:
        text = fallback.group(1).strip()
        return ForwardWatch(
            condition_text=text,
            watch_text=text,
            by_text=None,
        )
    return None


def extract_forward_watches(body: str) -> list[ForwardWatch]:
    """Parse ## Forward watches bullets from brief markdown."""
    if not body.strip():
        return []

    section_match = _FORWARD_SECTION.search(body)
    if section_match is None:
        return []

    tail = body[section_match.end() :]
    next_heading = re.search(r"^##\s+", tail, re.MULTILINE)
    section = tail[: next_heading.start()] if next_heading else tail

    watches: list[ForwardWatch] = []
    for line in section.splitlines():
        parsed = _parse_bullet(line)
        if parsed is not None:
            watches.append(parsed)
    return watches
