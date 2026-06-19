from __future__ import annotations

import pytest

from alloccontext.ingest.coinbase_client import normalize_coinbase_balances
from alloccontext.ingest.kraken_client import normalize_kraken_balances
from alloccontext.ingest.kraken_portfolio import portfolio_from_balances
from alloccontext.ingest.portfolio_holdings import build_holdings
from alloccontext.rollup.allocation_analysis import build_allocation_analysis
from alloccontext.mcp.handlers import get_context_bundle


def test_normalize_coinbase_balances_includes_alt_assets() -> None:
    accounts = [
        {
            "currency": "HYPE",
            "available_balance": {"value": "10"},
            "hold": {"value": "0"},
        },
        {
            "currency": "USDC",
            "available_balance": {"value": "100"},
            "hold": {"value": "0"},
        },
    ]
    balances, cash_breakdown = normalize_coinbase_balances(accounts)
    assert balances["HYPE"] == pytest.approx(10.0)
    assert balances["USD"] == pytest.approx(100.0)
    assert cash_breakdown["USDC"] == pytest.approx(100.0)


def test_normalize_kraken_balances_includes_alt_assets() -> None:
    raw = {"XXBT": "0.1", "HYPE": "5.0", "ZUSD": "250"}
    balances = normalize_kraken_balances(raw)
    assert balances["BTC"] == pytest.approx(0.1)
    assert balances["HYPE"] == pytest.approx(5.0)
    assert balances["USD"] == pytest.approx(250.0)


def test_build_holdings_marks_unpriced_assets() -> None:
    holdings, unrecognized = build_holdings(
        {"BTC": 1.0, "HYPE": 10.0, "USD": 100.0},
        {"BTC": 100.0},
    )
    hype = next(row for row in holdings if row["symbol"] == "HYPE")
    assert hype["price_usd"] is None
    assert hype["value_usd"] is None
    assert "HYPE" in unrecognized


def test_portfolio_from_balances_includes_hype_when_priced() -> None:
    snap = portfolio_from_balances(
        {"BTC": 1.0, "HYPE": 10.0, "USD": 0.0},
        {"BTC": 100.0, "HYPE": 25.0},
    )
    symbols = {row["symbol"] for row in snap.holdings}
    assert "HYPE" in symbols
    assert snap.nav_usd == pytest.approx(350.0)
    assert snap.unrecognized == []


def test_resolve_prices_for_balances_hype_via_cmc(monkeypatch) -> None:
    from alloccontext.ingest.portfolio_holdings import (
        build_holdings,
        resolve_prices_for_balances,
    )

    def fake_cmc(*, symbols, api_key, timeout):  # noqa: ARG001
        return {
            "HYPE": {
                "symbol": "HYPE",
                "quote": {"USD": {"price": "30.0"}},
            }
        }

    monkeypatch.setattr(
        "alloccontext.ingest.coinmarketcap.fetch_cmc_quotes",
        fake_cmc,
    )
    monkeypatch.setenv("COINMARKETCAP_API_KEY", "test-key")

    prices = resolve_prices_for_balances(
        {"HYPE": 2.0, "USD": 0.0},
        {},
        fetch_price=lambda _symbol: None,
    )
    assert prices["HYPE"] == pytest.approx(30.0)

    holdings, unrecognized = build_holdings({"HYPE": 2.0, "USD": 0.0}, prices)
    hype = next(row for row in holdings if row["symbol"] == "HYPE")
    assert hype["price_usd"] == pytest.approx(30.0)
    assert hype["value_usd"] == pytest.approx(60.0)
    assert unrecognized == []


def test_build_allocation_analysis_alt_symbol() -> None:
    analysis = build_allocation_analysis(
        {"BTC": 0.7, "HYPE": 0.2, "CASH": 0.1},
        {"BTC": 0.70, "HYPE": 0.15},
        0.05,
    )
    assert analysis["available"] is True
    assert analysis["drift"]["HYPE"] == pytest.approx(0.05)
    assert analysis["max_drift_symbol"] == "HYPE"
    assert analysis["rebalance_hint"] == "within_band"


def test_build_allocation_analysis_is_separate_block() -> None:
    analysis = build_allocation_analysis(
        {"BTC": 0.7, "ETH": 0.2, "CASH": 0.1},
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.00},
        0.15,
    )
    assert analysis["available"] is True
    assert "drift" in analysis
    assert "rebalance_hint" in analysis


def test_get_context_bundle_default_has_holdings_without_targets(conn, config) -> None:
    import json

    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "2026-05-21T12:00:00+00:00",
            10_000.0,
            500.0,
            json.dumps(
                {
                    "BTC": 0.7,
                    "ETH": 0.25,
                    "CASH": 0.05,
                    "prices": {"BTC": 70000.0, "ETH": 3000.0},
                }
            ),
            "{}",
        ),
    )
    conn.commit()
    bundle = get_context_bundle(conn, config, scope="daily", freshness="cached")
    portfolio = bundle["portfolio"]
    assert portfolio["available"] is True
    assert "holdings" in portfolio
    assert "target_allocation_pct" not in portfolio
    assert "drift" not in portfolio
    assert "allocation_analysis" not in bundle


def test_get_context_bundle_with_targets_attaches_analysis(conn, config) -> None:
    import json

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
    bundle = get_context_bundle(
        conn,
        config,
        scope="daily",
        freshness="cached",
        target_pct={"BTC": 0.70, "ETH": 0.30, "CASH": 0.00},
        band=0.15,
    )
    assert "allocation_analysis" in bundle
    assert bundle["allocation_analysis"]["rebalance_hint"]


def test_get_context_bundle_use_config_allocation_attaches_analysis(conn, config) -> None:
    import json

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
    bundle = get_context_bundle(
        conn,
        config,
        scope="daily",
        freshness="cached",
        use_config_allocation=True,
    )
    assert "allocation_analysis" in bundle
    assert bundle["allocation_analysis"]["target_allocation_pct"] == config.portfolio.target_allocations
    assert bundle["allocation_analysis"]["band"] == config.portfolio.rebalance_band
