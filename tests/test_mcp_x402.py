from __future__ import annotations

import pytest

from alloccontext.mcp.x402_config import (
    DEFAULT_MCP_PRICE,
    MCP_HTTP_PATH,
    CDP_FACILITATOR_URL,
    X402Settings,
    build_x402_facilitator_client,
    build_x402_routes,
    cdp_facilitator_configured,
    load_x402_settings,
)
from alloccontext.mcp.x402_pricing import DEFAULT_MCP_PRICE_HEAVY


def test_x402_disabled_without_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X402_PAY_TO", "0xabc")
    settings = load_x402_settings(require_payment=False)
    assert settings.enabled is False


def test_x402_requires_wallet_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("X402_PAY_TO", raising=False)
    with pytest.raises(RuntimeError, match="X402_PAY_TO"):
        load_x402_settings(require_payment=True)


def test_x402_enabled_with_wallet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X402_PAY_TO", "0xSeller")
    monkeypatch.setenv("X402_PRICE_MCP", "$0.03")
    settings = load_x402_settings(require_payment=True)
    assert settings.enabled is True
    assert settings.pay_to == "0xSeller"
    assert settings.mcp_price == "$0.03"


def test_x402_route_config() -> None:
    from alloccontext.mcp.x402_config import X402Settings

    settings = X402Settings(
        enabled=True,
        pay_to="0xSeller",
        facilitator_url="https://x402.org/facilitator",
        network="eip155:84532",
        mcp_price=DEFAULT_MCP_PRICE,
        mcp_price_heavy=DEFAULT_MCP_PRICE_HEAVY,
        mcp_path=MCP_HTTP_PATH,
    )
    routes = build_x402_routes(settings)
    assert f"POST {MCP_HTTP_PATH}" in routes
    accepts = routes[f"POST {MCP_HTTP_PATH}"].accepts
    assert accepts[0].pay_to == "0xSeller"
    assert all(opt.pay_to == "0xSeller" for opt in accepts)
    assert all(callable(opt.price) for opt in accepts)


def test_build_http_app_without_x402() -> None:
    pytest.importorskip("x402")
    from alloccontext.mcp.http import build_http_app

    app = build_http_app(x402=False)
    assert app is not None


def test_build_http_app_rejects_public_bind_without_x402() -> None:
    pytest.importorskip("x402")
    from alloccontext.mcp.http import build_http_app

    with pytest.raises(RuntimeError, match="non-loopback"):
        build_http_app(host="0.0.0.0", x402=False)


def test_build_http_app_allows_public_bind_with_self_host_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("x402")
    monkeypatch.setenv("ALLOC_CONTEXT_SELF_HOST_HTTP", "1")
    from alloccontext.mcp.http import build_http_app

    app = build_http_app(host="0.0.0.0", x402=False)
    assert app is not None


def test_build_http_app_allows_public_bind_with_x402(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("x402")
    monkeypatch.setenv("X402_PAY_TO", "0xSeller")
    from alloccontext.mcp.http import build_http_app

    app = build_http_app(host="0.0.0.0", x402=True)
    assert app is not None


def test_build_http_app_with_x402(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("x402")
    monkeypatch.setenv("X402_PAY_TO", "0xSeller")
    from alloccontext.mcp.http import build_http_app

    app = build_http_app(x402=True)
    assert app.user_middleware


def test_cdp_facilitator_does_not_auto_enable_x402_without_pay_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("x402")
    from alloccontext.mcp.http import build_http_app

    monkeypatch.delenv("X402_PAY_TO", raising=False)
    monkeypatch.delenv("X402_ENABLED", raising=False)
    monkeypatch.setenv("X402_FACILITATOR_URL", CDP_FACILITATOR_URL)
    app = build_http_app(x402=False)
    assert app is not None
    assert not app.user_middleware


def test_cdp_facilitator_client_requires_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("x402")
    pytest.importorskip("cdp")
    monkeypatch.delenv("CDP_API_KEY_ID", raising=False)
    monkeypatch.delenv("CDP_API_KEY_SECRET", raising=False)
    settings = X402Settings(
        enabled=True,
        pay_to="0xSeller",
        facilitator_url=CDP_FACILITATOR_URL,
        network="eip155:8453",
        mcp_price=DEFAULT_MCP_PRICE,
        mcp_path=MCP_HTTP_PATH,
    )
    with pytest.raises(RuntimeError, match="CDP_API_KEY"):
        build_x402_facilitator_client(settings)


def test_cdp_facilitator_client_with_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("x402")
    pytest.importorskip("cdp")
    monkeypatch.setenv("CDP_API_KEY_ID", "test-key-id")
    monkeypatch.setenv("CDP_API_KEY_SECRET", "test-key-secret")
    settings = X402Settings(
        enabled=True,
        pay_to="0xSeller",
        facilitator_url=CDP_FACILITATOR_URL,
        network="eip155:8453",
        mcp_price=DEFAULT_MCP_PRICE,
        mcp_path=MCP_HTTP_PATH,
    )
    client = build_x402_facilitator_client(settings)
    assert client.url == CDP_FACILITATOR_URL
    assert cdp_facilitator_configured()
