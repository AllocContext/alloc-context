from __future__ import annotations

from alloccontext.ingest.outcome import (
    classify_ingest_errors,
    ingest_ok,
    summarize_ingest_outcome,
)


def test_optional_source_failure_is_not_fatal() -> None:
    optional = frozenset({"fred", "coinmarketcap"})
    errors = {"fred": "HTTP 502"}
    fatal, optional_errors = classify_ingest_errors(errors, optional)
    assert fatal == {}
    assert optional_errors == errors
    ok, partial = ingest_ok(errors, optional)
    assert ok is True
    assert partial is True


def test_required_source_failure_is_fatal() -> None:
    optional = frozenset({"fred"})
    errors = {"kraken": "timeout"}
    fatal, optional_errors = classify_ingest_errors(errors, optional)
    assert fatal == errors
    assert optional_errors == {}
    ok, partial = ingest_ok(errors, optional)
    assert ok is False
    assert partial is False


def test_summarize_ingest_outcome_mixed() -> None:
    optional = frozenset({"fred"})
    outcome = summarize_ingest_outcome(
        {"fred": "502", "kraken": "down"},
        optional,
    )
    assert outcome["ok"] is False
    assert outcome["partial"] is False
    assert outcome["fatal_errors"] == {"kraken": "down"}
    assert outcome["optional_errors"] == {"fred": "502"}
