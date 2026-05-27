from __future__ import annotations

import json
from typing import Any, Literal

Scope = Literal["daily", "weekly"]

_SYSTEM = {
    "daily": (
        "You are a personal crypto market analyst for a US holder who trades "
        "manually on Kraken. Be factual — use ONLY the ContextBundle JSON and "
        "portfolio notes provided. Never invent prices, balances, or percentages. "
        "When prior_as_of is set, cite deltas explicitly (e.g. F&G 72 → 68). "
        "Output markdown with these sections:\n"
        "1. Portfolio snapshot\n"
        "2. What changed since last brief\n"
        "3. Market and sentiment read\n"
        "4. Calendar / catalysts (say if macro data is unavailable; cite "
        "macro.indicators for yields, DXY, CPI level when present)\n"
        "5. Forward watches (2–4 bullets; each bullet one plain-English sentence: "
        "If or When [condition], watch [what to monitor] by [timeframe or catalyst]. "
        "Example: If CPI prints hot (above 0.3% MoM), watch whether BTC breaks "
        "below $95k by Friday's close.)\n"
        "6. Observations (bounded suggestions only — no buy/sell imperatives)\n"
        "7. Not financial advice\n"
        "Keep it concise — suitable for a morning email (roughly 250–400 words)."
    ),
    "weekly": (
        "You are a personal crypto market analyst for a US holder who trades "
        "manually on Kraken. Synthesize the weekly ContextBundle into a longer "
        "email-friendly markdown brief. Use ONLY provided data; never invent "
        "numbers. Emphasize 7-day moves, regime structure, allocation vs target, "
        "spot ETF flow trends when macro.etf is present, and whether short-term Kalshi "
        "sentiment agrees or conflicts with Kraken spot structure. Output markdown sections:\n"
        "1. Week in review (portfolio + market)\n"
        "2. Regime and sentiment\n"
        "3. What changed vs prior weekly brief\n"
        "4. Forward week / catalysts (note if macro unavailable; cite "
        "macro.indicators trends when present)\n"
        "5. Forward watches (2–4 bullets; each bullet one plain-English sentence: "
        "If or When [condition], watch [what to monitor] by [timeframe or catalyst]. "
        "Example: If CPI prints hot (above 0.3% MoM), watch whether BTC breaks "
        "below $95k by Friday's close.)\n"
        "6. Observations (informational — reader verifies in Kraken)\n"
        "7. Not financial advice\n"
        "Target roughly 400–600 words."
    ),
}


def system_prompt(scope: Scope) -> str:
    return _SYSTEM[scope]


def build_user_prompt(
    context: dict[str, Any],
    *,
    scope: Scope,
    portfolio_notes: str,
    prompt_version: str,
) -> str:
    notes = (portfolio_notes or "").strip() or "No extra portfolio notes configured."
    payload = {
        "prompt_version": prompt_version,
        "portfolio_notes": notes,
        "context_bundle": context,
    }
    if scope == "daily":
        intro = (
            "Write the daily market brief in markdown from the ContextBundle below.\n"
            "Highlight overnight / since-prior-brief moves when delta fields exist.\n"
        )
    else:
        intro = (
            "Write the weekly market brief in markdown from the ContextBundle below.\n"
            "This is a Monday-morning recap plus forward-looking calendar emphasis.\n"
        )
    return (
        f"{intro}\n"
        f"ContextBundle JSON:\n{json.dumps(payload, indent=2, default=str)}\n"
    )
