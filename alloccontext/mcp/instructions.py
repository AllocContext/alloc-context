from __future__ import annotations

PRODUCT_INSTRUCTIONS = (
    "AllocContext: portfolio-first crypto context for agents. Portfolio from CEX "
    "keys or a public EVM wallet address (keyless). Default responses include "
    "holdings[], market, sentiment, macro, regime, and delta. Allocation "
    "drift and rebalance are opt-in via target_pct or allocation_analysis. "
    "Privacy: nothing stored; one-time read-only; pass-through only. "
    "setup objects explain missing config."
)

REBALANCE_HINT_GUIDE = (
    "rebalance_hint codes (in allocation_analysis when opted in): within_band — "
    "drift inside band; consider_deploy_cash — cash above target; "
    "consider_trim_to_cash — cash below target; consider_rebalance — drift "
    "exceeds band."
)
