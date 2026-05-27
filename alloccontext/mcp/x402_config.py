from __future__ import annotations

import os
from dataclasses import dataclass

from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.constants import DEFAULT_FACILITATOR_URL
from x402.http.types import PaymentOption, RouteConfig
from x402.server import x402ResourceServer

CDP_FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402"
DEFAULT_NETWORK = "eip155:84532"  # Base Sepolia
DEFAULT_MCP_PRICE = "$0.02"
MCP_HTTP_PATH = "/mcp"


@dataclass(frozen=True)
class X402Settings:
    enabled: bool
    pay_to: str
    facilitator_url: str
    network: str
    mcp_price: str
    mcp_path: str = MCP_HTTP_PATH


def load_x402_settings(*, require_payment: bool = False) -> X402Settings:
    pay_to = os.environ.get("X402_PAY_TO", "").strip()
    if require_payment and not pay_to:
        raise RuntimeError("X402_PAY_TO is required when x402 is enabled")

    facilitator_url = os.environ.get("X402_FACILITATOR_URL", DEFAULT_FACILITATOR_URL).strip()
    network = os.environ.get("X402_NETWORK", DEFAULT_NETWORK).strip()
    mcp_price = os.environ.get("X402_PRICE_MCP", DEFAULT_MCP_PRICE).strip()
    enabled = require_payment and bool(pay_to)

    return X402Settings(
        enabled=enabled,
        pay_to=pay_to,
        facilitator_url=facilitator_url,
        network=network,
        mcp_price=mcp_price,
        mcp_path=os.environ.get("X402_MCP_PATH", MCP_HTTP_PATH).strip() or MCP_HTTP_PATH,
    )


def build_x402_resource_server(settings: X402Settings) -> x402ResourceServer:
    from x402.mechanisms.evm.exact import ExactEvmServerScheme

    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.facilitator_url))
    server = x402ResourceServer(facilitator)
    server.register(settings.network, ExactEvmServerScheme())
    return server


def build_x402_routes(settings: X402Settings) -> dict[str, RouteConfig]:
    option = PaymentOption(
        scheme="exact",
        pay_to=settings.pay_to,
        price=settings.mcp_price,
        network=settings.network,
    )
    return {
        f"POST {settings.mcp_path}": RouteConfig(
            accepts=[option],
            mime_type="application/json",
            description=(
                "AllocContext MCP — BTC/ETH market context, rebalance moves, "
                "and allocation band checks (facts only)."
            ),
        ),
    }


def cdp_facilitator_configured() -> bool:
    return bool(os.environ.get("CDP_API_KEY_ID") and os.environ.get("CDP_API_KEY_SECRET"))
