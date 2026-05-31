from __future__ import annotations

from unittest.mock import patch

from alloccontext.ingest.runner import run_ingest
from alloccontext.mcp.handlers import get_context_bundle


def test_run_ingest_fatal_when_kraken_primary_missing_credentials(
    config, conn, monkeypatch
) -> None:
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    with patch("alloccontext.ingest.runner.refresh_fear_greed", return_value={"ok": True, "rows": 1}), patch(
        "alloccontext.ingest.runner.refresh_kalshi",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_macro_calendar",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_etf_flows",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_coingecko",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_coinmarketcap",
        return_value={"ok": True, "rows": 0},
    ), patch(
        "alloccontext.ingest.runner.refresh_fred",
        return_value={"ok": True, "rows": 1},
    ), patch(
        "alloccontext.ingest.runner.refresh_coinbase",
        return_value={"ok": True, "rows": 0, "skipped": True, "reason": "exchange_disabled"},
    ):
        result = run_ingest(conn, config)

    assert result["ok"] is False
    assert result["fatal_errors"].get("kraken") == "missing_kraken_credentials"


def test_live_market_context_fail_closed(config, conn, monkeypatch, mock_live_ingest_ok) -> None:
    monkeypatch.setattr(
        "alloccontext.ingest.alt_quotes.refresh_alt_quotes",
        lambda _c, _cfg, symbols: {
            "ok": False,
            "rows": 0,
            "symbols_requested": symbols,
            "symbols_fetched": [],
            "symbols_missing": list(symbols),
        },
    )
    from alloccontext.mcp.handlers import get_market_context

    from alloccontext.mcp.contracts import validate_tool_response

    payload = get_market_context(
        conn,
        config,
        freshness="live",
        assets=["HYPE"],
    )
    assert payload.get("available") is False
    assert payload.get("reason") == "live_alt_quote_refresh_failed"
    validate_tool_response("get_market_context", payload)


def test_live_context_bundle_fail_closed_on_ingest(config, conn, monkeypatch) -> None:
    monkeypatch.setattr(
        "alloccontext.ingest.runner.run_ingest",
        lambda _c, _cfg: {
            "ok": False,
            "errors": {"kraken": "missing_kraken_credentials"},
            "counts": {},
            "fatal_errors": {"kraken": "missing_kraken_credentials"},
        },
    )
    payload = get_context_bundle(conn, config, freshness="live")
    assert payload.get("available") is False
    assert payload.get("reason") == "live_ingest_failed"
    assert payload["ingest"]["ok"] is False


def test_live_market_context_fail_closed_on_ingest(config, conn, monkeypatch) -> None:
    from alloccontext.mcp.handlers import get_market_context

    monkeypatch.setattr(
        "alloccontext.ingest.runner.run_ingest",
        lambda _c, _cfg: {
            "ok": False,
            "errors": {"kraken": "missing_kraken_credentials"},
            "counts": {},
            "fatal_errors": {"kraken": "missing_kraken_credentials"},
        },
    )
    payload = get_market_context(conn, config, freshness="live")
    assert payload.get("available") is False
    assert payload.get("reason") == "live_ingest_failed"
