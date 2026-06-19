from __future__ import annotations

import pytest

from alloccontext.mcp.assets import (
    apply_assets_filter_to_bundle,
    filter_delta_market,
    filter_market_assets,
    resolve_view_assets,
    validate_view_assets,
)
from alloccontext.mcp.handlers import get_context_bundle, get_rebalance_plan
from alloccontext.rollup.context import build_context_bundle
from alloccontext.rollup.regime import build_regime_context


def test_validate_view_assets_defaults_to_btc_eth() -> None:
    assert validate_view_assets(None) == ("BTC", "ETH")
    assert validate_view_assets([]) == ("BTC", "ETH")


def test_validate_view_assets_ignores_unknown_asset() -> None:
    assert validate_view_assets(["BTC", "HYPE"]) == ("BTC",)
    assert resolve_view_assets(["BTC", "HYPE"]) == (("BTC",), ("HYPE",))


def test_resolve_view_assets_hype_only_falls_back_to_default() -> None:
    assert resolve_view_assets(["HYPE"]) == (("BTC", "ETH"), ("HYPE",))


def test_get_market_context_ignores_unsupported_portfolio_asset(conn, config) -> None:
    from alloccontext.mcp.handlers import get_market_context

    payload = get_market_context(
        conn,
        config,
        scope="daily",
        freshness="cached",
        assets=["BTC", "ETH", "HYPE"],
    )
    assert payload["assets"] == ["BTC", "ETH"]
    assert payload["assets_omitted"] == ["HYPE"]
    assert "market" in payload
    assert "sentiment" in payload


def test_filter_market_assets_subset() -> None:
    market = {
        "available": True,
        "assets": {
            "btc": {"price_usd": 100.0},
            "eth": {"price_usd": 50.0},
        },
    }
    filtered = filter_market_assets(market, ("BTC",))
    assert "eth" not in filtered["assets"]
    assert filtered["assets"]["btc"]["price_usd"] == 100.0


def test_build_regime_context_includes_allocation_hint() -> None:
    regime = build_regime_context(
        portfolio={
            "available": True,
            "allocation_analysis": {
                "available": True,
                "rebalance_hint": "within_band",
                "outside_band": False,
                "max_drift": 0.02,
                "band": 0.15,
                "target_allocation_pct": {"BTC": 0.7, "ETH": 0.3, "CASH": 0.0},
            },
        },
        sentiment={"available": False},
        delta={"available": False},
        prior_as_of=None,
    )
    assert regime["available"] is False
    assert regime["allocation"]["hint"] == "within_band"
    assert any(hint["kind"] == "allocation" for hint in regime["hints"])


def test_build_regime_context_risk_off_ignores_portfolio_cash() -> None:
    """ADR-020: cash weight must not inflate market risk_off score."""
    high_cash = build_regime_context(
        portfolio={
            "available": True,
            "allocation_pct": {"BTC": 0.10, "ETH": 0.10, "CASH": 0.80},
            "rebalance_hint": "consider_rebalance",
        },
        sentiment={"available": False},
        delta={"available": False},
        prior_as_of=None,
    )
    neutral_fg = build_regime_context(
        portfolio={"available": True, "allocation_pct": {"CASH": 0.80}},
        sentiment={
            "available": True,
            "fear_greed": {"value": 50, "classification": "Neutral"},
        },
        delta={"available": False},
        prior_as_of=None,
    )
    assert high_cash["risk_off"]["score"] == 0
    assert high_cash["risk_off"]["level"] == "low"
    assert not high_cash["risk_off"]["signals"]
    assert neutral_fg["risk_off"]["score"] == 0
    assert neutral_fg["risk_off"]["level"] == "low"


def test_build_regime_context_risk_off_from_fear_greed_only() -> None:
    regime = build_regime_context(
        portfolio={"available": False},
        sentiment={
            "available": True,
            "fear_greed": {"value": 20, "classification": "Extreme Fear"},
        },
        delta={"available": False},
        prior_as_of=None,
    )
    assert regime["available"] is True
    assert regime["risk_off"]["score"] == 35
    assert regime["risk_off"]["level"] == "low"
    assert any("Fear & Greed" in signal for signal in regime["risk_off"]["signals"])


def test_build_context_bundle_includes_regime(conn, config) -> None:
    bundle = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
    )
    assert "regime" in bundle
    assert "hints" in bundle["regime"]


def test_get_context_bundle_assets_filter_and_target_override(conn, config) -> None:
    bundle = get_context_bundle(
        conn,
        config,
        scope="daily",
        freshness="cached",
        assets=["BTC"],
        target_pct={"BTC": 0.80, "ETH": 0.20, "CASH": 0.0},
        band=0.10,
    )
    assert bundle["assets"] == ["BTC"]
    assert bundle["target_pct"]["BTC"] == 0.80
    assert bundle["band"] == 0.10
    if bundle.get("market", {}).get("available"):
        assert "eth" not in bundle["market"].get("assets", {})


def test_filter_delta_market_shifts_without_market_block() -> None:
    delta = {
        "available": True,
        "notable_shifts": [
            "BTC spot +2.1% since prior snapshot",
            "ETH spot -0.8% since prior snapshot",
        ],
    }
    filtered = filter_delta_market(delta, ("BTC",))
    assert filtered["notable_shifts"] == ["BTC spot +2.1% since prior snapshot"]


def test_assets_filter_aligns_regime_delta_hints() -> None:
    bundle = {
        "portfolio": {"available": False},
        "sentiment": {"available": False},
        "delta": {
            "available": True,
            "notable_shifts": [
                "BTC spot +2.1% since prior snapshot",
                "ETH spot -0.8% since prior snapshot",
            ],
        },
        "prior_as_of": "2026-05-20T12:00:00+00:00",
    }
    filtered = apply_assets_filter_to_bundle(bundle, ("BTC",))
    regime = build_regime_context(
        portfolio=filtered.get("portfolio") or {},
        sentiment=filtered.get("sentiment") or {},
        delta=filtered.get("delta") or {},
        prior_as_of=filtered.get("prior_as_of"),
    )
    shift_text = " ".join(regime["comparison"].get("notable_shifts") or [])
    assert "BTC" in shift_text
    assert "ETH" not in shift_text


def test_get_rebalance_plan_optional_band_check() -> None:
    result = get_rebalance_plan(
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
        1000.0,
        band=0.15,
    )
    assert "band_check" in result
    assert result["band_check"]["hint"] == "within_band"
