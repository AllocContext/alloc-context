from __future__ import annotations

from alloccontext.ingest.outcome import (
    classify_ingest_errors,
    ingest_ok,
    skipped_source_error,
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


def test_skipped_required_source_is_error() -> None:
    optional = frozenset({"fred"})
    result = {"ok": True, "skipped": True, "reason": "rate_limited"}
    assert skipped_source_error("coingecko", result, optional) == "rate_limited"
    assert skipped_source_error("fred", result, optional) is None
    assert (
        skipped_source_error(
            "social",
            {"ok": True, "skipped": True, "reason": "not_implemented"},
            optional,
        )
        is None
    )


def test_skipped_exchange_disabled_not_error() -> None:
    optional = frozenset()
    result = {"ok": True, "skipped": True, "reason": "exchange_disabled"}
    assert skipped_source_error("kraken", result, optional) is None
