from __future__ import annotations

from typing import Any


def normalize_optional_feed_name(feed: str) -> str:
    """Map per-asset SoSoValue feed keys to the configured optional source name."""
    if feed.startswith("sosovalue_"):
        return "sosovalue"
    return feed


def skipped_source_error(
    source: str,
    result: dict[str, Any],
    optional_sources: frozenset[str],
) -> str | None:
    """Map required-source skips to ingest errors."""
    if not result.get("skipped"):
        return None
    if source in optional_sources:
        return None
    reason = str(result.get("reason") or "skipped")
    if reason in {"exchange_disabled", "not_implemented"}:
        return None
    return reason


def optional_feed_errors(
    result: dict[str, Any],
    optional_sources: frozenset[str],
) -> dict[str, str]:
    errors: dict[str, str] = {}
    for feed, message in (result.get("feed_errors") or {}).items():
        name = normalize_optional_feed_name(str(feed))
        if name in optional_sources:
            errors[name] = str(message)
    return errors


def ingest_errors_from_source(
    source: str,
    result: dict[str, Any],
    optional_sources: frozenset[str],
) -> dict[str, str]:
    """Collect per-source and optional-feed errors for ingest outcome classification."""
    skip_error = skipped_source_error(source, result, optional_sources)
    if skip_error:
        return {source: skip_error}

    feed_optional = optional_feed_errors(result, optional_sources)

    if result.get("ok") or result.get("skipped"):
        return feed_optional

    if source in optional_sources:
        errors = {source: str(result.get("error") or "failed")}
        errors.update(feed_optional)
        return errors

    # Parent failed: only optional feeds failed — do not fail ingest on the parent.
    if feed_optional and not any(
        normalize_optional_feed_name(str(feed)) not in optional_sources
        for feed in (result.get("feed_errors") or {})
    ):
        return feed_optional

    errors = {source: str(result.get("error") or "failed")}
    errors.update(feed_optional)
    return errors


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
