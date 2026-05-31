from __future__ import annotations

import pytest

from alloccontext.mcp.handlers import check_band, get_rebalance_plan, validate_freshness
from alloccontext.mcp.validation import McpValidationError, validate_band, validate_target_pct


def test_validate_freshness_cached() -> None:
    assert validate_freshness("cached") == "cached"


def test_validate_freshness_live() -> None:
    assert validate_freshness("live") == "live"


def test_validate_freshness_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="freshness must be"):
        validate_freshness("stale")


def test_validate_target_pct_requires_sum_to_one() -> None:
    with pytest.raises(McpValidationError, match="sum"):
        validate_target_pct({"BTC": 0.5, "ETH": 0.3, "CASH": 0.1})


def test_validate_band_rejects_out_of_range() -> None:
    with pytest.raises(McpValidationError, match="band"):
        validate_band(1.5)


def test_get_rebalance_plan_rejects_non_positive_nav() -> None:
    with pytest.raises(McpValidationError, match="nav_usd"):
        get_rebalance_plan(
            {"BTC": 0.7, "ETH": 0.2, "CASH": 0.1},
            {"BTC": 0.65, "ETH": 0.20, "CASH": 0.15},
            nav_usd=0,
        )


def test_check_band_rejects_invalid_target() -> None:
    with pytest.raises(McpValidationError, match="sum"):
        check_band(
            {"BTC": 0.7, "ETH": 0.2, "CASH": 0.1},
            {"BTC": 0.5, "ETH": 0.3, "CASH": 0.1},
            band=0.15,
        )
