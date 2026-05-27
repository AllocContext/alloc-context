from __future__ import annotations

from alloccontext.rollup.rebalance import compute_rebalance_plan, format_rebalance_plan


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
    assert "BTC 65%, ETH 20%, Cash 15%" in text
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


def test_coinbase_move_wording() -> None:
    plan = compute_rebalance_plan(
        1000.0,
        {"BTC": 0.613, "ETH": 0.163, "CASH": 0.224},
        {"BTC": 0.65, "ETH": 0.20, "CASH": 0.15},
        exchange="coinbase",
    )
    assert plan["exchange"] == "coinbase"
    assert all("BTC-USD" in line or "ETH-USD" in line for line in plan["moves"])
