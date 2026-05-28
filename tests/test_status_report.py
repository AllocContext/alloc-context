from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from alloccontext.status_report import (
    build_status_report,
    format_age,
    format_status_report,
    probe_mcp_health,
)
from alloccontext.store.db import record_ingest_run


def test_format_age() -> None:
    assert format_age(30) == "30s ago"
    assert format_age(120) == "2m ago"
    assert format_age(7200) == "2h ago"
    assert format_age(200_000) == "2d ago"
    assert format_age(None) == "unknown"


def test_ingest_and_source_health_share_age_seconds(config, conn) -> None:
    now = "2026-05-28T12:00:00+00:00"
    record_ingest_run(
        conn,
        source="kraken",
        started_at=now,
        finished_at=now,
        rows_upserted=10,
        error=None,
    )
    report = build_status_report(config, conn, probe_mcp=False)
    kraken_ingest = next(
        r for r in report["ingest"]["required"] if r["source"] == "kraken"
    )
    assert kraken_ingest["age_seconds"] == report["source_health"]["kraken"]["age_seconds"]


def test_build_status_report_classifies_required_and_optional(config, conn) -> None:
    now = "2026-05-28T12:00:00+00:00"
    for name, enabled in config.ingest.sources.items():
        if not enabled or name in config.ingest.optional_sources:
            continue
        record_ingest_run(
            conn,
            source=name,
            started_at=now,
            finished_at=now,
            rows_upserted=1,
            error=None,
        )
    record_ingest_run(
        conn,
        source="finnhub",
        started_at=now,
        finished_at=now,
        rows_upserted=0,
        error="HTTP 403",
    )
    report = build_status_report(config, conn, probe_mcp=False)
    required_names = {row["source"] for row in report["ingest"]["required"]}
    optional_names = {row["source"] for row in report["ingest"]["optional"]}
    assert "kraken" in required_names
    assert "finnhub" in optional_names
    assert report["ingest_ok"] is True
    assert "finnhub" in report["optional_failures"]


def test_build_status_report_fails_on_missing_required_run(config, conn) -> None:
    report = build_status_report(config, conn, probe_mcp=False)
    assert report["ingest_ok"] is False
    assert report["ok"] is False
    kraken = next(r for r in report["ingest"]["required"] if r["source"] == "kraken")
    assert kraken["never_run"] is True


def test_format_status_report_includes_sections(config, conn) -> None:
    now = "2026-05-28T12:00:00+00:00"
    record_ingest_run(
        conn,
        source="kraken",
        started_at=now,
        finished_at=now,
        rows_upserted=1,
        error=None,
    )
    report = build_status_report(config, conn, probe_mcp=False)
    text = format_status_report(report)
    assert "Ingest (required)" in text
    assert "Context snapshots" in text
    assert "MCP /health: (probe skipped)" in text


def test_probe_mcp_health_success() -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "ok": True,
        "ingest_ok": True,
        "source_health": {"kraken": {"ok": True}},
    }
    with patch("alloccontext.status_report.requests.get", return_value=response):
        result = probe_mcp_health("http://127.0.0.1:8000/health")
    assert result["ok"] is True
    assert result["reachable"] is True
    assert result["ingest_ok"] is True


def test_probe_mcp_health_unreachable() -> None:
    with patch(
        "alloccontext.status_report.requests.get",
        side_effect=requests.ConnectionError("connection refused"),
    ):
        result = probe_mcp_health("http://127.0.0.1:8000/health")
    assert result["ok"] is False
    assert result["reachable"] is False
