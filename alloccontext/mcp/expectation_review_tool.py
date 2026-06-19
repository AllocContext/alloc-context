"""Shared envelope helpers for get_expectation_review responses."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from alloccontext.mcp.staleness import with_staleness
from alloccontext.timeutil import utc_now


def envelope_expectation_review(
    payload: dict[str, Any],
    *,
    scope: str,
    freshness: str,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ensure scope, freshness, and staleness keys required by the tool contract."""
    out = dict(payload)
    out["scope"] = scope
    out.setdefault("freshness", freshness)
    if source is not None:
        if source.get("as_of"):
            out.setdefault("as_of", source["as_of"])
        if source.get("age_seconds") is not None:
            out.setdefault("age_seconds", source["age_seconds"])
    if "as_of" in out and "age_seconds" in out:
        return out
    now = utc_now().replace(microsecond=0)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    stripped = {k: v for k, v in out.items() if k not in ("as_of", "age_seconds")}
    return with_staleness(stripped, as_of=now)
