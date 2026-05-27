from __future__ import annotations

import pytest

from alloccontext.mcp.x402_config import (
    DEFAULT_MCP_PRICE,
    MCP_HTTP_PATH,
    build_x402_routes,
    load_x402_settings,
)


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
        mcp_path=MCP_HTTP_PATH,
    )
    routes = build_x402_routes(settings)
    assert f"POST {MCP_HTTP_PATH}" in routes
    assert routes[f"POST {MCP_HTTP_PATH}"].accepts[0].pay_to == "0xSeller"


def test_build_http_app_without_x402() -> None:
    pytest.importorskip("x402")
    from alloccontext.mcp.http import build_http_app

    app = build_http_app(x402=False)
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
    from alloccontext.mcp.x402_config import CDP_FACILITATOR_URL

    monkeypatch.delenv("X402_PAY_TO", raising=False)
    monkeypatch.delenv("X402_ENABLED", raising=False)
    monkeypatch.setenv("X402_FACILITATOR_URL", CDP_FACILITATOR_URL)
    app = build_http_app(x402=False)
    assert app is not None
    assert not app.user_middleware
