from __future__ import annotations

import json
from pathlib import Path

import pytest

from alloccontext.mcp.contracts import MCP_TOOL_NAMES, validate_tool_response
from alloccontext.mcp.handlers import (
    check_allocation_bands,
    check_band,
    get_context_at,
    get_context_bundle,
    get_context_delta,
    get_market_context,
    get_rebalance_plan,
)
from alloccontext.rollup.context import build_context_bundle

_FIXTURES = Path(__file__).parent / "fixtures" / "mcp"


def test_mcp_tool_names_match_bazaar_registry() -> None:
    listed = json.loads((_FIXTURES / "tool_names.json").read_text())
    assert frozenset(listed) == MCP_TOOL_NAMES


def test_validate_context_bundle_golden_keys() -> None:
    golden = json.loads((_FIXTURES / "context_bundle_keys.json").read_text())
    stub = {
        key: (
            {"available": False, "reason": "stub"}
            if key in ("portfolio", "market", "sentiment", "macro", "delta", "regime")
            else None
        )
        for key in golden
    }
    stub["freshness"] = "cached"
    validate_tool_response("get_context_bundle", stub)


def test_get_context_bundle_contract(conn, config) -> None:
    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "2026-05-21T12:00:00+00:00",
            10_000.0,
            500.0,
            json.dumps({"BTC": 0.7, "ETH": 0.25, "CASH": 0.05}),
            "{}",
        ),
    )
    conn.commit()
    payload = get_context_bundle(conn, config, scope="daily", freshness="cached")
    validate_tool_response("get_context_bundle", payload)


def test_get_market_context_contract(conn, config) -> None:
    payload = get_market_context(conn, config, scope="daily", freshness="cached")
    validate_tool_response("get_market_context", payload)


def test_live_alt_refresh_failure_contracts(config, conn, monkeypatch) -> None:
    refresh_result = {
        "ok": False,
        "rows": 0,
        "symbols_requested": ["HYPE"],
        "symbols_fetched": [],
        "symbols_missing": ["HYPE"],
    }
    monkeypatch.setattr(
        "alloccontext.ingest.alt_quotes.refresh_alt_quotes",
        lambda _c, _cfg, symbols: refresh_result,
    )
    bundle = get_context_bundle(conn, config, freshness="live", assets=["HYPE"])
    market = get_market_context(conn, config, freshness="live", assets=["HYPE"])
    validate_tool_response("get_context_bundle", bundle)
    validate_tool_response("get_market_context", market)
    assert bundle["reason"] == "live_alt_quote_refresh_failed"
    assert market["reason"] == "live_alt_quote_refresh_failed"


def test_get_rebalance_plan_contract() -> None:
    payload = get_rebalance_plan(
        {"BTC": 0.60, "ETH": 0.30, "CASH": 0.10},
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.00},
        10_000.0,
        band=0.15,
    )
    validate_tool_response("get_rebalance_plan", payload)


def test_check_allocation_band_contract() -> None:
    payload = check_band(
        {"BTC": 0.60, "ETH": 0.30, "CASH": 0.10},
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.00},
        0.15,
    )
    validate_tool_response("check_allocation_band", payload)


def test_check_allocation_bands_contract() -> None:
    payload = check_allocation_bands(
        {"BTC": 0.65, "ETH": 0.30, "CASH": 0.05},
        [
            {
                "name": "base",
                "target_pct": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.00},
                "band": 0.15,
            }
        ],
    )
    validate_tool_response("check_allocation_bands", payload)


def test_get_context_at_contract(conn, config) -> None:
    bundle = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=True,
    )
    loaded = get_context_at(
        conn,
        config,
        scope="daily",
        as_of=bundle["as_of"],
        match="exact",
    )
    validate_tool_response("get_context_at", loaded)


def test_get_context_at_unavailable_contract(conn, config) -> None:
    payload = get_context_at(
        conn,
        config,
        scope="daily",
        as_of="1999-01-01T00:00:00+00:00",
        match="exact",
    )
    validate_tool_response("get_context_at", payload)


def test_get_context_delta_contract(conn, config) -> None:
    first = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=True,
    )
    second = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=True,
    )
    payload = get_context_delta(
        conn,
        config,
        scope="daily",
        prior_as_of=first["as_of"],
        current_as_of=second["as_of"],
    )
    validate_tool_response("get_context_delta", payload)


def test_get_portfolio_state_unavailable_contract(config) -> None:
    from alloccontext.mcp.handlers import get_portfolio_state

    payload = get_portfolio_state(
        config,
        exchange="kraken",
        api_key="bad",
        api_secret="bad",
    )
    validate_tool_response("get_portfolio_state", payload)


def test_validate_tool_response_rejects_unknown_tool() -> None:
    with pytest.raises(ValueError, match="unknown MCP tool"):
        validate_tool_response("nonexistent_tool", {})
