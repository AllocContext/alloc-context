from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

from alloccontext.rollup.rebalance import compute_rebalance_plan, format_rebalance_plan
from alloccontext.synthesize.openai import ChatFn, openai_chat

logger = logging.getLogger(__name__)

AdviceFn = Callable[..., str]


def _pct_label(fraction: float) -> str:
    return f"{round(fraction * 100):.0f}%"


def asset_label(asset: str) -> str:
    if asset == "CASH":
        return "Cash"
    return asset


def _format_allocation(allocation: dict[str, float]) -> str:
    parts = []
    for asset in ("BTC", "ETH", "CASH"):
        if asset in allocation:
            parts.append(f"{asset_label(asset)} {_pct_label(allocation[asset])}")
    return ", ".join(parts)


def _normalize_allocations(
    btc: float,
    eth: float,
    cash: float,
) -> dict[str, float]:
    total = btc + eth + cash
    if total <= 0:
        return {"BTC": 0.0, "ETH": 0.0, "CASH": 1.0}
    return {
        "BTC": round(btc / total, 4),
        "ETH": round(eth / total, 4),
        "CASH": round(cash / total, 4),
    }


def _infer_regime(context: dict[str, Any], *, hint: str) -> str:
    """Return risk_on, cautious, or risk_off from ContextBundle fields."""
    score = 0

    fg = (context.get("sentiment") or {}).get("fear_greed") or {}
    fg_value = fg.get("value")
    if isinstance(fg_value, (int, float)):
        if fg_value >= 60:
            score += 1
        elif fg_value <= 35:
            score -= 1

    kalshi = (context.get("sentiment") or {}).get("kalshi") or {}
    vol = kalshi.get("volatility_regime")
    if vol == "high":
        score -= 2
    elif vol == "medium":
        score -= 1
    elif vol == "low":
        score += 1

    tape = str(kalshi.get("tape_summary") or "").lower()
    if "broad down" in tape or "leaning down" in tape:
        score -= 1
    elif "broad up" in tape or "leaning up" in tape:
        score += 1

    if hint == "consider_trim_to_cash":
        score -= 1
    elif hint == "consider_deploy_cash":
        score += 1

    if score >= 2:
        return "risk_on"
    if score <= -2:
        return "risk_off"
    return "cautious"


def _suggested_allocations(
    config,
    *,
    regime: str,
) -> dict[str, float]:
    target = dict(config.portfolio.target_allocations)
    btc_tgt = float(target.get("BTC") or 0)
    eth_tgt = float(target.get("ETH") or 0)
    cash_tgt = float(target.get("CASH") or 0)
    max_cash = float(config.portfolio.max_cash_risk_off)

    if regime == "risk_on":
        return _normalize_allocations(btc_tgt, eth_tgt, cash_tgt)

    crypto_sum = btc_tgt + eth_tgt or 1.0
    if regime == "risk_off":
        cash = max_cash
        remaining = max(0.0, 1.0 - cash)
        return _normalize_allocations(
            remaining * btc_tgt / crypto_sum,
            remaining * eth_tgt / crypto_sum,
            cash,
        )

    cash = min(max_cash, max(cash_tgt, 0.30))
    remaining = max(0.0, 1.0 - cash)
    return _normalize_allocations(
        remaining * btc_tgt / crypto_sum,
        remaining * eth_tgt / crypto_sum,
        cash,
    )


def _regime_phrase(regime: str) -> str:
    if regime == "risk_on":
        return "risk-on"
    if regime == "risk_off":
        return "risk-off / defensive"
    return "mixed / cautious"


def _alloc_key(allocation: dict[str, float]) -> tuple[float, float, float]:
    return (
        round(float(allocation.get("BTC") or 0), 4),
        round(float(allocation.get("ETH") or 0), 4),
        round(float(allocation.get("CASH") or 0), 4),
    )


def _portfolio_from_context(context: dict[str, Any]) -> dict[str, Any]:
    return context.get("portfolio") if isinstance(context.get("portfolio"), dict) else {}


def _append_rebalance_plans(
    prose: str,
    context: dict[str, Any],
    config,
    *,
    suggested: dict[str, float],
) -> str:
    portfolio = _portfolio_from_context(context)
    nav = float(portfolio.get("nav_usd") or 0)
    current = portfolio.get("allocation_pct") or {}
    if nav <= 0 or not current:
        return prose.strip()

    config_target = dict(config.portfolio.target_allocations)
    blocks = [prose.strip()]
    config_plan = compute_rebalance_plan(nav, current, config_target)
    blocks.append(format_rebalance_plan(config_plan, target_pct=config_target))

    if _alloc_key(suggested) != _alloc_key(config_target):
        suggested_plan = compute_rebalance_plan(nav, current, suggested)
        blocks.append(format_rebalance_plan(suggested_plan, target_pct=suggested))

    return "\n\n".join(block for block in blocks if block)


def fallback_allocation_advice(
    context: dict[str, Any],
    config,
    *,
    hint: str,
) -> str:
    regime = _infer_regime(context, hint=hint)
    suggested = _suggested_allocations(config, regime=regime)
    fg = ((context.get("sentiment") or {}).get("fear_greed") or {}).get("value")
    tape = ((context.get("sentiment") or {}).get("kalshi") or {}).get("tape_summary")

    climate_bits = [f"Tape looks {_regime_phrase(regime)}"]
    if fg is not None:
        climate_bits.append(f"Fear & Greed at {fg}")
    if tape:
        climate_bits.append(str(tape).rstrip("."))

    climate = ". ".join(climate_bits) + "."
    prose = (
        f"{climate} Given current conditions, consider shifting toward "
        f"**{_format_allocation(suggested)}**."
    )
    return _append_rebalance_plans(prose, context, config, suggested=suggested)


def _system_prompt() -> str:
    return (
        "You advise a US crypto holder who trades manually on Kraken. "
        "Use ONLY the ContextBundle JSON and portfolio notes provided. "
        "Never invent prices, balances, or indicators. "
        "Write 2–3 plain-English sentences for an allocation band alert email:\n"
        "1. One sentence on current market climate (cite fear_greed, kalshi tape, "
        "market moves, macro when present).\n"
        "2. One sentence suggesting target allocation percentages for BTC, ETH, and "
        "Cash that sum to 100%. Use 'consider shifting toward BTC X%, ETH Y%, "
        "Cash Z%' language — not buy/sell imperatives. Do not repeat the config "
        "target allocations; the email already lists current vs target above.\n"
        "3. Optionally one short sentence tying the suggestion to rebalance_hint.\n"
        "Do not compute USD amounts — rebalance_plan in the payload has exact "
        "Kraken move lines you must not contradict.\n"
        "Respect portfolio.max_cash_risk_off as an upper cash bound in defensive "
        "conditions. Do not use markdown headers or bullet lists."
    )


def _build_prompt(
    context: dict[str, Any],
    config,
    *,
    hint: str,
) -> str:
    portfolio = _portfolio_from_context(context)
    nav = float(portfolio.get("nav_usd") or 0)
    current = portfolio.get("allocation_pct") or {}
    config_target = dict(config.portfolio.target_allocations)
    regime = _infer_regime(context, hint=hint)
    suggested = _suggested_allocations(config, regime=regime)

    rebalance_plans: dict[str, Any] = {
        "to_config_target": compute_rebalance_plan(nav, current, config_target),
    }
    if _alloc_key(suggested) != _alloc_key(config_target):
        rebalance_plans["to_context_suggested"] = compute_rebalance_plan(
            nav, current, suggested
        )

    payload = {
        "rebalance_hint": hint,
        "portfolio_notes": (config.portfolio.notes or "").strip()
        or "No extra portfolio notes configured.",
        "target_allocations": config_target,
        "context_suggested_allocations": suggested,
        "max_cash_risk_off": config.portfolio.max_cash_risk_off,
        "rebalance_band": config.portfolio.rebalance_band,
        "rebalance_plans": rebalance_plans,
        "context_bundle": context,
    }
    return (
        "Write allocation guidance for this band-breach alert.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}\n"
    )


def synthesize_allocation_advice(
    context: dict[str, Any],
    config,
    *,
    hint: str,
    llm_call: AdviceFn | None = None,
) -> str:
    if not config.synthesis.enabled or not os.environ.get("OPENAI_API_KEY"):
        return fallback_allocation_advice(context, config, hint=hint)

    call: ChatFn = llm_call or openai_chat
    regime = _infer_regime(context, hint=hint)
    suggested = _suggested_allocations(config, regime=regime)
    try:
        prose = call(
            _build_prompt(context, config, hint=hint),
            config.synthesis,
            system=_system_prompt(),
        )
        return _append_rebalance_plans(prose, context, config, suggested=suggested)
    except Exception as exc:  # noqa: BLE001 — fall back on any LLM/network failure
        logger.warning("Allocation advice LLM failed: %s", exc)
        return fallback_allocation_advice(context, config, hint=hint)
