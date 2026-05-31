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


def test_health_default_omits_source_health() -> None:
    app = build_http_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "ingest_ok" in body
    assert "source_health" not in body


def test_health_verbose_includes_source_health(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    from alloccontext.mcp.http import _make_health_handler

    monkeypatch.setenv("ALLOC_CONTEXT_HEALTH_VERBOSE", "1")
    handler = _make_health_handler(None)
    request = MagicMock()
    request.client.host = "127.0.0.1"
    response = handler(request)
    assert response.status_code == 200
    body = response.body.decode()
    import json

    payload = json.loads(body)
    assert "ingest_ok" in payload
    assert "source_health" in payload


def test_health_verbose_omits_source_health_off_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import MagicMock

    from alloccontext.mcp.http import _make_health_handler

    monkeypatch.setenv("ALLOC_CONTEXT_HEALTH_VERBOSE", "1")
    handler = _make_health_handler(None)
    request = MagicMock()
    request.client.host = "203.0.113.50"
    response = handler(request)
    import json

    payload = json.loads(response.body.decode())
    assert "ingest_ok" in payload
    assert "source_health" not in payload


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


def test_live_context_bundle_serves_without_alt_request(config, conn, mock_live_ingest_ok) -> None:
    from alloccontext.mcp.contracts import validate_tool_response

    result = get_context_bundle(conn, config, freshness="live")
    assert result.get("available") is not False
    validate_tool_response("get_context_bundle", result)
