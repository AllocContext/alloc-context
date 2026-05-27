from __future__ import annotations

import asyncio

import pytest
from starlette.requests import Request
from x402.http.middleware.fastapi import FastAPIAdapter
from x402.http.types import HTTPRequestContext

from alloccontext.mcp.x402_pricing import (
    DEFAULT_MCP_PRICE_HEAVY,
    build_mcp_dynamic_price,
    mcp_call_is_heavy,
)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (None, False),
        ({}, False),
        ({"method": "initialize"}, False),
        (
            {
                "method": "tools/call",
                "params": {
                    "name": "get_market_context",
                    "arguments": {"scope": "daily", "freshness": "cached"},
                },
            },
            False,
        ),
        (
            {
                "method": "tools/call",
                "params": {
                    "name": "get_context_bundle",
                    "arguments": {"scope": "daily", "freshness": "live"},
                },
            },
            True,
        ),
        (
            {
                "method": "tools/call",
                "params": {
                    "name": "get_portfolio_state",
                    "arguments": {"exchange": "kraken"},
                },
            },
            True,
        ),
    ],
)
def test_mcp_call_is_heavy(body: dict | None, expected: bool) -> None:
    assert mcp_call_is_heavy(body) is expected


async def _price_for_body(body: dict) -> str:
    import json

    payload = json.dumps(body).encode()
    scope = {"type": "http", "method": "POST", "path": "/mcp", "headers": []}
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": payload, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)
    context = HTTPRequestContext(
        adapter=FastAPIAdapter(request),
        path="/mcp",
        method="POST",
    )
    resolve = build_mcp_dynamic_price(light_price="$0.02", heavy_price="$0.05")
    return await resolve(context)


def test_mcp_dynamic_price_light() -> None:
    price = asyncio.run(
        _price_for_body(
            {
                "method": "tools/call",
                "params": {
                    "name": "get_rebalance_plan",
                    "arguments": {"allocation_pct": {}, "target_pct": {}, "nav_usd": 1},
                },
            }
        )
    )
    assert price == "$0.02"


def test_mcp_dynamic_price_heavy_portfolio() -> None:
    price = asyncio.run(
        _price_for_body(
            {
                "method": "tools/call",
                "params": {
                    "name": "get_portfolio_state",
                    "arguments": {"exchange": "kraken"},
                },
            }
        )
    )
    assert price == "$0.05"


def test_mcp_dynamic_price_heavy_live_freshness() -> None:
    price = asyncio.run(
        _price_for_body(
            {
                "method": "tools/call",
                "params": {
                    "name": "get_market_context",
                    "arguments": {"scope": "daily", "freshness": "live"},
                },
            }
        )
    )
    assert price == "$0.05"


def test_request_json_survives_dynamic_price_read() -> None:
    async def exercise() -> None:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_portfolio_state",
                "arguments": {"exchange": "kraken"},
            },
        }
        price = await _price_for_body(body)
        assert price == "$0.05"

        import json

        payload = json.dumps(body).encode()
        scope = {"type": "http", "method": "POST", "path": "/mcp", "headers": []}
        sent = False

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": payload, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(scope, receive)
        resolve = build_mcp_dynamic_price(light_price="$0.02", heavy_price="$0.05")
        context = HTTPRequestContext(
            adapter=FastAPIAdapter(request),
            path="/mcp",
            method="POST",
        )
        await resolve(context)
        reread = await request.json()
        assert reread["params"]["name"] == "get_portfolio_state"

    asyncio.run(exercise())


def test_x402_heavy_price_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from alloccontext.mcp.x402_config import load_x402_settings

    monkeypatch.setenv("X402_PAY_TO", "0xSeller")
    monkeypatch.setenv("X402_PRICE_MCP_HEAVY", "$0.07")
    settings = load_x402_settings(require_payment=True)
    assert settings.mcp_price_heavy == "$0.07"
    assert DEFAULT_MCP_PRICE_HEAVY == "$0.05"
