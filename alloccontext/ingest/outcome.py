from __future__ import annotations

from typing import Any


def classify_ingest_errors(
    errors: dict[str, str],
    optional_sources: frozenset[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Split failures into required (fatal) vs optional (non-fatal)."""
    fatal: dict[str, str] = {}
    optional: dict[str, str] = {}
    for source, message in errors.items():
        if source in optional_sources:
            optional[source] = message
        else:
            fatal[source] = message
    return fatal, optional


def ingest_ok(
    errors: dict[str, str],
    optional_sources: frozenset[str],
) -> tuple[bool, bool]:
    fatal, optional = classify_ingest_errors(errors, optional_sources)
    ok = not fatal
    partial = ok and bool(optional)
    return ok, partial


def summarize_ingest_outcome(
    errors: dict[str, str],
    optional_sources: frozenset[str],
) -> dict[str, Any]:
    fatal, optional = classify_ingest_errors(errors, optional_sources)
    ok, partial = ingest_ok(errors, optional_sources)
    return {
        "ok": ok,
        "partial": partial,
        "errors": errors,
        "fatal_errors": fatal,
        "optional_errors": optional,
    }
