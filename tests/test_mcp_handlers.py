from __future__ import annotations

from alloccontext.mcp.handlers import check_band, get_rebalance_plan
from alloccontext.rollup.band import check_allocation_band


def test_check_allocation_band_within() -> None:
    result = check_allocation_band(
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
        0.15,
    )
    assert result["outside_band"] is False
    assert result["hint"] == "within_band"


def test_check_allocation_band_outside() -> None:
    result = check_allocation_band(
        {"BTC": 0.60, "ETH": 0.25, "CASH": 0.15},
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
        0.10,
    )
    assert result["outside_band"] is True
    assert result["hint"] == "consider_rebalance"
    assert result["max_drift_symbol"] == "CASH"


def test_mcp_check_band_includes_staleness() -> None:
    result = check_band(
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
        0.15,
    )
    assert "as_of" in result
    assert "age_seconds" in result
    assert result["hint"] == "within_band"


def test_mcp_rebalance_plan_includes_staleness() -> None:
    result = get_rebalance_plan(
        {"BTC": 0.613, "ETH": 0.163, "CASH": 0.224},
        {"BTC": 0.65, "ETH": 0.20, "CASH": 0.15},
        1000.0,
    )
    assert result["available"] is True
    assert "as_of" in result
    assert "moves" in result
