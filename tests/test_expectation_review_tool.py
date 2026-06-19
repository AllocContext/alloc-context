from __future__ import annotations

from alloccontext.mcp.contracts import validate_tool_response
from alloccontext.mcp.expectation_review_tool import envelope_expectation_review


def test_envelope_expectation_review_unavailable() -> None:
    payload = envelope_expectation_review(
        {"available": False, "reason": "no_theses_supplied"},
        scope="daily",
        freshness="cached",
    )
    validate_tool_response("get_expectation_review", payload)
    assert payload["scope"] == "daily"
    assert payload["freshness"] == "cached"


def test_envelope_expectation_review_preserves_upstream_staleness() -> None:
    payload = envelope_expectation_review(
        {
            "available": False,
            "reason": "live_ingest_failed",
            "freshness": "live",
            "as_of": "2026-06-01T12:00:00+00:00",
            "age_seconds": 120,
        },
        scope="weekly",
        freshness="live",
        source={
            "as_of": "2026-06-01T12:00:00+00:00",
            "age_seconds": 120,
        },
    )
    validate_tool_response("get_expectation_review", payload)
    assert payload["scope"] == "weekly"
