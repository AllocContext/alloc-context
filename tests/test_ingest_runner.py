from __future__ import annotations

from unittest.mock import patch

from alloccontext.ingest.runner import run_ingest
from alloccontext.store.status import ingest_status


def test_run_ingest_fear_greed_and_kraken(config, conn, monkeypatch) -> None:
    monkeypatch.setenv("KRAKEN_API_KEY", "test-key")
    monkeypatch.setenv("KRAKEN_API_SECRET", "dGVzdA==")
    fg_rows = [{"timestamp": 1_700_000_000, "value": 55, "classification": "Neutral"}]

    with patch(
        "alloccontext.ingest.runner.refresh_fear_greed",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_kraken",
        return_value={"ok": True, "rows": 721, "market_bars": 720},
    ), patch(
        "alloccontext.ingest.runner.refresh_kalshi",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_macro_calendar",
        return_value={"ok": True, "rows": 9},
    ), patch(
        "alloccontext.ingest.runner.refresh_etf_flows",
        return_value={"ok": True, "rows": 4},
    ), patch(
        "alloccontext.ingest.runner.refresh_coingecko",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_coinmarketcap",
        return_value={"ok": True, "rows": 0, "skipped": True},
    ), patch(
        "alloccontext.ingest.runner.refresh_fred",
        return_value={"ok": True, "rows": 24},
    ):
        result = run_ingest(conn, config)

    assert result["ok"] is True
    assert result["counts"]["fear_greed"] == 1
    assert result["counts"]["kraken"] == 721
    assert result["counts"]["kalshi"] == 1
    status = ingest_status(conn)
    assert "fear_greed" in status["last_ingest_by_source"]
    assert "kraken" in status["last_ingest_by_source"]
    assert "kalshi" in status["last_ingest_by_source"]


def test_run_ingest_optional_source_failure_still_ok(config, conn, monkeypatch) -> None:
    monkeypatch.setenv("KRAKEN_API_KEY", "test-key")
    monkeypatch.setenv("KRAKEN_API_SECRET", "dGVzdA==")
    with patch(
        "alloccontext.ingest.runner.refresh_fear_greed",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_kraken",
        return_value={"ok": True, "rows": 721, "market_bars": 720},
    ), patch(
        "alloccontext.ingest.runner.refresh_kalshi",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_macro_calendar",
        return_value={"ok": True, "rows": 9},
    ), patch(
        "alloccontext.ingest.runner.refresh_etf_flows",
        return_value={"ok": True, "rows": 4},
    ), patch(
        "alloccontext.ingest.runner.refresh_coingecko",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_coinmarketcap",
        return_value={"ok": True, "rows": 0, "skipped": True},
    ), patch(
        "alloccontext.ingest.runner.refresh_fred",
        return_value={"ok": False, "error": "HTTP 502", "rows": 256},
    ):
        result = run_ingest(conn, config)

    assert result["ok"] is True
    assert result["partial"] is True
    assert result["optional_errors"]["fred"] == "HTTP 502"


def test_run_ingest_dry_run(config, conn) -> None:
    result = run_ingest(conn, config, dry_run=True)
    assert result["dry_run"] is True
    assert sum(result["counts"].values()) == 0
