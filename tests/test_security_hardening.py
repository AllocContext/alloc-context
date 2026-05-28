from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient
from x402.http.middleware.fastapi import FastAPIAdapter
from x402.http.types import HTTPRequestContext

from alloccontext.config import _validate_kalshi_base_url
from alloccontext.ingest.http_errors import redact_url_secrets
from alloccontext.mcp.handlers import get_context_bundle
from alloccontext.mcp.http import build_http_app
from alloccontext.mcp.x402_config import MCP_HTTP_PATH, load_x402_settings
from alloccontext.mcp.x402_pricing import build_mcp_dynamic_price


def test_redact_url_secrets() -> None:
    url = "https://example.com/calendar?from=2026-01-01&token=secret123"
    redacted = redact_url_secrets(url)
    assert "secret123" not in redacted
    assert "token=" in redacted and "secret123" not in redacted


def test_validate_kalshi_base_url_rejects_http() -> None:
    with pytest.raises(ValueError, match="https"):
        _validate_kalshi_base_url("http://api.elections.kalshi.com/trade-api/v2")


def test_validate_kalshi_base_url_rejects_unknown_host() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        _validate_kalshi_base_url("https://169.254.169.254/trade-api/v2")


def test_load_x402_settings_rejects_custom_mcp_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X402_PAY_TO", "0xSeller")
    monkeypatch.setenv("X402_MCP_PATH", "/paid/mcp")
    with pytest.raises(RuntimeError, match=MCP_HTTP_PATH):
        load_x402_settings(require_payment=True)


def test_health_minimal_omits_source_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOC_CONTEXT_HEALTH_MINIMAL", "1")
    app = build_http_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "ingest_ok" in body
    assert "source_health" not in body


async def _heavy_price_for_invalid_json() -> str:
    scope = {"type": "http", "method": "POST", "path": "/mcp", "headers": []}

    async def receive():
        return {"type": "http.request", "body": b"not-json", "more_body": False}

    request = Request(scope, receive)
    context = HTTPRequestContext(
        adapter=FastAPIAdapter(request),
        path="/mcp",
        method="POST",
    )
    resolve = build_mcp_dynamic_price(light_price="$0.02", heavy_price="$0.05")
    return await resolve(context)


def test_unparseable_mcp_body_prices_heavy() -> None:
    price = asyncio.run(_heavy_price_for_invalid_json())
    assert price == "$0.05"


def test_live_context_bundle_fails_on_fatal_ingest(config, conn, monkeypatch) -> None:
    monkeypatch.setattr(
        "alloccontext.ingest.runner.run_ingest",
        lambda _conn, _config: {
            "ok": False,
            "fatal_errors": {"kraken": "timeout"},
            "errors": {"kraken": "timeout"},
            "counts": {},
        },
    )
    from alloccontext.mcp.contracts import validate_tool_response

    result = get_context_bundle(conn, config, freshness="live")
    assert result.get("available") is False
    assert result.get("reason") == "live_ingest_failed"
    assert result["fatal_errors"] == {"kraken": "timeout"}
    validate_tool_response("get_context_bundle", result)
