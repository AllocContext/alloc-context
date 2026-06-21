from __future__ import annotations

from alloccontext.mcp.setup import (
    allocation_not_configured,
    bridge_upstream_retired,
    portfolio_not_configured,
    upstream_payment_required,
)


def test_portfolio_not_configured_shape() -> None:
    payload = portfolio_not_configured()
    assert payload["available"] is False
    assert payload["reason"] == "portfolio_not_configured"
    assert "setup" in payload
    assert payload["setup"]["privacy_note"]


def test_upstream_payment_required_shape() -> None:
    payload = upstream_payment_required()
    assert payload["reason"] == "upstream_payment_required"
    assert payload["setup"]["feature"] == "x402_payment"


def test_allocation_not_configured_shape() -> None:
    payload = allocation_not_configured()
    assert payload["reason"] == "allocation_not_configured"
    assert "target_allocation" in payload["setup"]["example"]


def test_bridge_upstream_retired_shape() -> None:
    payload = bridge_upstream_retired()
    assert payload["available"] is False
    assert payload["reason"] == "upstream_retired"
    assert payload["setup"]["docs"] == "docs/cursor-mcp.md"
