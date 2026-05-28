from __future__ import annotations

from alloccontext.config import DEFAULT_OPTIONAL_INGEST_SOURCES
from alloccontext.ingest.outcome import (
    classify_ingest_errors,
    ingest_errors_from_source,
    ingest_ok,
    normalize_optional_feed_name,
    skipped_source_error,
    summarize_ingest_outcome,
)

OPTIONAL = DEFAULT_OPTIONAL_INGEST_SOURCES


def test_optional_source_failure_is_not_fatal() -> None:
    errors = {"fred": "HTTP 502"}
    fatal, optional_errors = classify_ingest_errors(errors, OPTIONAL)
    assert fatal == {}
    assert optional_errors == errors
    ok, partial = ingest_ok(errors, OPTIONAL)
    assert ok is True
    assert partial is True


def test_required_source_failure_is_fatal() -> None:
    errors = {"kraken": "timeout"}
    fatal, optional_errors = classify_ingest_errors(errors, OPTIONAL)
    assert fatal == errors
    assert optional_errors == {}
    ok, partial = ingest_ok(errors, OPTIONAL)
    assert ok is False
    assert partial is False


def test_summarize_ingest_outcome_mixed() -> None:
    outcome = summarize_ingest_outcome(
        {"fred": "502", "kraken": "down"},
        OPTIONAL,
    )
    assert outcome["ok"] is False
    assert outcome["partial"] is False
    assert outcome["fatal_errors"] == {"kraken": "down"}
    assert outcome["optional_errors"] == {"fred": "502"}


def test_skipped_optional_breadth_sources_not_fatal() -> None:
    result = {"ok": True, "skipped": True, "reason": "coingecko_rate_limited"}
    assert skipped_source_error("coingecko", result, OPTIONAL) is None
    assert skipped_source_error("coinmarketcap", result, OPTIONAL) is None
    assert skipped_source_error("fred", result, OPTIONAL) is None


def test_skipped_required_source_is_error() -> None:
    result = {"ok": True, "skipped": True, "reason": "rate_limited"}
    assert skipped_source_error("kraken", result, OPTIONAL) == "rate_limited"
    assert (
        skipped_source_error(
            "social",
            {"ok": True, "skipped": True, "reason": "not_implemented"},
            OPTIONAL,
        )
        is None
    )


def test_skipped_exchange_disabled_not_error() -> None:
    optional = frozenset()
    result = {"ok": True, "skipped": True, "reason": "exchange_disabled"}
    assert skipped_source_error("kraken", result, optional) is None


def test_normalize_sosovalue_feed_name() -> None:
    assert normalize_optional_feed_name("sosovalue_btc") == "sosovalue"
    assert normalize_optional_feed_name("finnhub") == "finnhub"


def test_optional_feed_errors_on_successful_parent() -> None:
    result = {
        "ok": True,
        "rows": 9,
        "feed_errors": {"finnhub": "HTTP 429", "fmp": "timeout"},
    }
    errors = ingest_errors_from_source("macro_calendar", result, OPTIONAL)
    assert errors == {"finnhub": "HTTP 429", "fmp": "timeout"}


def test_etf_flows_only_sosovalue_failure_not_fatal() -> None:
    result = {
        "ok": False,
        "rows": 0,
        "error": "etf_ingest_failed",
        "feed_errors": {"sosovalue_btc": "HTTP 502", "sosovalue_eth": "HTTP 502"},
    }
    errors = ingest_errors_from_source("etf_flows", result, OPTIONAL)
    assert errors == {"sosovalue": "HTTP 502"}
    ok, partial = ingest_ok(errors, OPTIONAL)
    assert ok is True
    assert partial is True
