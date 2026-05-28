"""Stable required-key contracts for MCP tool JSON responses."""

from __future__ import annotations

from typing import Any

from alloccontext.mcp.bazaar import mcp_tool_specs

STALENESS_KEYS = ("as_of", "age_seconds")

PORTFOLIO_AVAILABLE_KEYS = (
    "available",
    "nav_usd",
    "cash_usd",
    "allocation_pct",
    "target_allocation_pct",
    "drift",
    "rebalance_hint",
    "outside_band",
    "max_drift",
    "band",
)

REGIME_AVAILABLE_KEYS = (
    "available",
    "summary",
    "hints",
    "allocation",
)

MCP_TOOL_NAMES = frozenset(spec["tool_name"] for spec in mcp_tool_specs())


def _missing_keys(payload: dict[str, Any], required: tuple[str, ...]) -> list[str]:
    return [key for key in required if key not in payload]


def assert_has_keys(
    payload: dict[str, Any],
    required: tuple[str, ...],
    *,
    label: str,
) -> None:
    missing = _missing_keys(payload, required)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{label} missing keys: {joined}")


def assert_available_block(
    block: dict[str, Any],
    *,
    label: str,
    when_available: tuple[str, ...] = (),
    when_unavailable: tuple[str, ...] = ("available",),
) -> None:
    assert_has_keys(block, ("available",), label=label)
    if block.get("available"):
        if when_available:
            assert_has_keys(block, when_available, label=f"{label} (available)")
    else:
        assert_has_keys(block, when_unavailable, label=f"{label} (unavailable)")


LIVE_INGEST_UNAVAILABLE_KEYS = (
    "available",
    "reason",
    "fatal_errors",
    "ingest",
    "freshness",
    *STALENESS_KEYS,
)


def validate_context_bundle(payload: dict[str, Any]) -> None:
    if payload.get("available") is False:
        assert_has_keys(
            payload,
            LIVE_INGEST_UNAVAILABLE_KEYS,
            label="get_context_bundle",
        )
        return
    assert_has_keys(
        payload,
        (
            "bundle_id",
            "scope",
            "as_of",
            "horizon_days",
            "portfolio",
            "market",
            "sentiment",
            "macro",
            "delta",
            "regime",
            "freshness",
            *STALENESS_KEYS,
        ),
        label="get_context_bundle",
    )
    assert_available_block(
        payload["portfolio"],
        label="portfolio",
        when_available=PORTFOLIO_AVAILABLE_KEYS,
    )
    assert_available_block(
        payload["regime"],
        label="regime",
        when_available=REGIME_AVAILABLE_KEYS,
    )


def validate_market_context(payload: dict[str, Any]) -> None:
    if payload.get("available") is False:
        assert_has_keys(
            payload,
            LIVE_INGEST_UNAVAILABLE_KEYS,
            label="get_market_context",
        )
        return
    assert_has_keys(
        payload,
        (
            "scope",
            "freshness",
            "market",
            "sentiment",
            "macro",
            "etf",
            "breadth",
            *STALENESS_KEYS,
        ),
        label="get_market_context",
    )
    for name in ("market", "sentiment", "macro", "etf", "breadth"):
        assert_available_block(payload[name], label=name)


def validate_rebalance_plan(payload: dict[str, Any]) -> None:
    assert_has_keys(payload, (*STALENESS_KEYS,), label="get_rebalance_plan")
    if payload.get("available") is False:
        assert_has_keys(payload, ("available", "reason"), label="get_rebalance_plan")
        return
    assert_has_keys(
        payload,
        (
            "available",
            "exchange",
            "nav_usd",
            "allocation_pct",
            "target_pct",
            "moves",
            "delta_usd",
            *STALENESS_KEYS,
        ),
        label="get_rebalance_plan",
    )


def validate_check_allocation_band(payload: dict[str, Any]) -> None:
    assert_has_keys(
        payload,
        ("outside_band", "hint", "max_drift", "drift", *STALENESS_KEYS),
        label="check_allocation_band",
    )


def validate_check_allocation_bands(payload: dict[str, Any]) -> None:
    assert_has_keys(
        payload,
        ("allocation_pct", "scenarios", *STALENESS_KEYS),
        label="check_allocation_bands",
    )
    for index, scenario in enumerate(payload["scenarios"]):
        assert_has_keys(
            scenario,
            ("name", "target_pct", "band", "outside_band", "hint"),
            label=f"check_allocation_bands.scenarios[{index}]",
        )


CONTEXT_AT_FOUND_KEYS = (
    "bundle_id",
    "scope",
    "as_of",
    "horizon_days",
    "portfolio",
    "market",
    "sentiment",
    "macro",
    "delta",
    "regime",
    "snapshot_as_of",
    "requested_as_of",
    "match",
)


def validate_context_at(payload: dict[str, Any]) -> None:
    if payload.get("available") is False:
        assert_has_keys(
            payload,
            ("available", "reason", "scope", "requested_as_of", "match"),
            label="get_context_at",
        )
        return
    assert_has_keys(payload, CONTEXT_AT_FOUND_KEYS, label="get_context_at")
    assert_available_block(
        payload["portfolio"],
        label="portfolio",
        when_available=PORTFOLIO_AVAILABLE_KEYS,
    )
    assert_available_block(
        payload["regime"],
        label="regime",
        when_available=REGIME_AVAILABLE_KEYS,
    )


def validate_context_delta(payload: dict[str, Any]) -> None:
    if payload.get("available") is False:
        assert_has_keys(
            payload,
            ("available", "reason", "scope", "prior_as_of"),
            label="get_context_delta",
        )
        return
    assert_has_keys(
        payload,
        (
            "scope",
            "prior_as_of",
            "current_as_of",
            "notable_shifts",
            "prior_snapshot_as_of",
            "current_snapshot_as_of",
        ),
        label="get_context_delta",
    )


def validate_portfolio_state(payload: dict[str, Any]) -> None:
    assert_has_keys(payload, (*STALENESS_KEYS,), label="get_portfolio_state")
    if not payload.get("available"):
        assert_has_keys(
            payload,
            ("available", "exchange", "source", "reason", *STALENESS_KEYS),
            label="get_portfolio_state",
        )
        return
    assert_has_keys(
        payload,
        (
            "available",
            "exchange",
            "source",
            "nav_usd",
            "allocation_pct",
            "target_allocation_pct",
            "drift",
            "rebalance_hint",
            *STALENESS_KEYS,
        ),
        label="get_portfolio_state",
    )


_VALIDATORS = {
    "get_context_bundle": validate_context_bundle,
    "get_market_context": validate_market_context,
    "get_rebalance_plan": validate_rebalance_plan,
    "check_allocation_band": validate_check_allocation_band,
    "check_allocation_bands": validate_check_allocation_bands,
    "get_context_at": validate_context_at,
    "get_context_delta": validate_context_delta,
    "get_portfolio_state": validate_portfolio_state,
}


def validate_tool_response(tool_name: str, payload: dict[str, Any]) -> None:
    if tool_name not in MCP_TOOL_NAMES:
        raise ValueError(f"unknown MCP tool: {tool_name}")
    validator = _VALIDATORS.get(tool_name)
    if validator is None:
        raise ValueError(f"no contract validator for tool: {tool_name}")
    validator(payload)
