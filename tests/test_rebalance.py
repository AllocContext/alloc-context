from __future__ import annotations

from alloccontext.rollup.rebalance import (
    compute_rebalance_plan,
    format_rebalance_plan,
    format_target_pct_header,
)


def test_deploy_cash_split_to_btc_and_eth() -> None:
    """User example: 22.4/61.3/16.3 -> 15/65/20 on $1,000 NAV."""
    plan = compute_rebalance_plan(
        1000.0,
        {"BTC": 0.613, "ETH": 0.163, "CASH": 0.224},
        {"BTC": 0.65, "ETH": 0.20, "CASH": 0.15},
    )
    assert plan["available"] is True
    assert plan["delta_usd"]["CASH"] == -74.0
    assert plan["delta_usd"]["BTC"] == 37.0
    assert plan["delta_usd"]["ETH"] == 37.0
    assert plan["moves"] == [
        "Deploy ~$37 from cash → XBT",
        "Deploy ~$37 from cash → ETH",
    ]


def test_rebalance_plan_trims_overweight_alt() -> None:
    plan = compute_rebalance_plan(
        1000.0,
        {"BTC": 0.60, "HYPE": 0.15, "CASH": 0.25},
        {"BTC": 0.65, "HYPE": 0.10, "CASH": 0.25},
    )
    assert plan["delta_usd"]["HYPE"] == -50.0
    assert any("HYPE" in line and "Sell" in line for line in plan["moves"])


def test_rebalance_plan_deploys_cash_to_alt() -> None:
    plan = compute_rebalance_plan(
        1000.0,
        {"BTC": 0.50, "HYPE": 0.05, "CASH": 0.45},
        {"BTC": 0.50, "HYPE": 0.15, "CASH": 0.35},
    )
    assert plan["delta_usd"]["HYPE"] == 100.0
    assert any("HYPE" in line for line in plan["moves"])


def test_format_rebalance_plan_includes_target_and_nav() -> None:
    plan = compute_rebalance_plan(
        640.0,
        {"BTC": 0.613, "ETH": 0.163, "CASH": 0.224},
        {"BTC": 0.65, "ETH": 0.20, "CASH": 0.15},
    )
    text = format_rebalance_plan(
        plan,
        target_pct={"BTC": 0.65, "ETH": 0.20, "CASH": 0.15},
    )
    assert "BTC 65%" in text
    assert "ETH 20%" in text
    assert "Cash 15%" in text
    assert "$640" in text
    assert "Deploy ~$" in text


def test_trim_when_overweight() -> None:
    plan = compute_rebalance_plan(
        1000.0,
        {"BTC": 0.80, "ETH": 0.15, "CASH": 0.05},
        {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
    )
    assert any("Sell" in line for line in plan["moves"])
    assert any("BTC" in line or "XBT" in line for line in plan["moves"])


def test_stable_keys_collapse_for_plan_math() -> None:
    plan = compute_rebalance_plan(
        1000.0,
        {"BTC": 0.50, "USDC": 0.50},
        {"BTC": 0.60, "CASH": 0.40},
    )
    assert plan["delta_usd"]["BTC"] == 100.0
    assert plan["delta_usd"]["CASH"] == -100.0
    assert any("Deploy" in line for line in plan["moves"])


def test_format_header_collapses_stable_targets() -> None:
    header = format_target_pct_header({"BTC": 0.7, "USDC": 0.2, "CASH": 0.1})
    assert "Cash 30%" in header
    assert "USDC" not in header


def test_coinbase_move_wording() -> None:
    plan = compute_rebalance_plan(
        1000.0,
        {"BTC": 0.613, "ETH": 0.163, "CASH": 0.224},
        {"BTC": 0.65, "ETH": 0.20, "CASH": 0.15},
        exchange="coinbase",
    )
    assert plan["exchange"] == "coinbase"
    assert all("BTC-USD" in line or "ETH-USD" in line for line in plan["moves"])
