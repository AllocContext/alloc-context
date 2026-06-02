from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from alloccontext.mcp.bazaar import (
    LISTING_DESCRIPTION,
    build_http_route_extensions,
    public_mcp_url,
    resolve_public_base_url,
)
from alloccontext.mcp.x402_pricing import DEFAULT_MCP_PRICE_HEAVY
from alloccontext.mcp.x402_stables import (
    build_payment_options_for_stables,
    effective_accepted_stable_symbols,
    load_accepted_stable_symbols,
)
from x402.extensions.bazaar import bazaar_resource_server_extension
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.constants import DEFAULT_FACILITATOR_URL
from x402.http.types import RouteConfig
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
    mcp_price_heavy: str = DEFAULT_MCP_PRICE_HEAVY
    mcp_path: str = MCP_HTTP_PATH
    accepted_stables: tuple[str, ...] = ()


def load_x402_settings(*, require_payment: bool = False) -> X402Settings:
    pay_to = os.environ.get("X402_PAY_TO", "").strip()
    if require_payment and not pay_to:
        raise RuntimeError("X402_PAY_TO is required when x402 is enabled")

    facilitator_url = os.environ.get("X402_FACILITATOR_URL", DEFAULT_FACILITATOR_URL).strip()
    network = os.environ.get("X402_NETWORK", DEFAULT_NETWORK).strip()
    mcp_price = os.environ.get("X402_PRICE_MCP", DEFAULT_MCP_PRICE).strip()
    mcp_price_heavy = os.environ.get(
        "X402_PRICE_MCP_HEAVY", DEFAULT_MCP_PRICE_HEAVY
    ).strip()
    mcp_path = os.environ.get("X402_MCP_PATH", MCP_HTTP_PATH).strip() or MCP_HTTP_PATH
    if mcp_path != MCP_HTTP_PATH:
        raise RuntimeError(
            f"X402_MCP_PATH must be {MCP_HTTP_PATH!r} (got {mcp_path!r}); "
            "custom paths are unsupported until the MCP HTTP mount is configurable"
        )
    enabled = require_payment and bool(pay_to)

    return X402Settings(
        enabled=enabled,
        pay_to=pay_to,
        facilitator_url=facilitator_url,
        network=network,
        mcp_price=mcp_price,
        mcp_price_heavy=mcp_price_heavy,
        mcp_path=mcp_path,
        accepted_stables=load_accepted_stable_symbols(),
    )


def _is_cdp_facilitator_url(url: str) -> bool:
    return url.rstrip("/").startswith(CDP_FACILITATOR_URL.rstrip("/"))


def _normalize_cdp_api_secret(raw: str) -> str:
    secret = raw.strip()
    if len(secret) >= 2 and secret[0] == secret[-1] and secret[0] in ('"', "'"):
        secret = secret[1:-1]
    if "\\n" in secret:
        secret = secret.replace("\\n", "\n")
    return secret.strip()


def load_cdp_api_credentials(
    env: Mapping[str, str] | None = None,
) -> tuple[str, str] | None:
    source = env if env is not None else os.environ
    api_key_id = source.get("CDP_API_KEY_ID", "").strip()
    secret = source.get("CDP_API_KEY_SECRET", "").strip()
    if not secret:
        secret_file = source.get("CDP_API_KEY_SECRET_FILE", "").strip()
        if secret_file:
            try:
                secret = Path(secret_file).read_text(encoding="utf-8")
            except OSError as exc:
                raise RuntimeError(
                    f"CDP_API_KEY_SECRET_FILE not readable: {secret_file} ({exc})"
                ) from exc
    if not api_key_id or not secret:
        return None
    return api_key_id, _normalize_cdp_api_secret(secret)


def build_x402_facilitator_client(settings: X402Settings) -> HTTPFacilitatorClient:
    if _is_cdp_facilitator_url(settings.facilitator_url):
        try:
            from cdp.x402 import create_facilitator_config
        except ImportError as exc:
            raise RuntimeError(
                "CDP facilitator requires cdp-sdk (pip install 'alloc-context[hosted]')"
            ) from exc
        credentials = load_cdp_api_credentials()
        if not credentials:
            raise RuntimeError(
                "CDP facilitator requires CDP_API_KEY_ID and CDP_API_KEY_SECRET "
                "(or CDP_API_KEY_SECRET_FILE)"
            )
        api_key_id, api_key_secret = credentials
        return HTTPFacilitatorClient(
            create_facilitator_config(api_key_id, api_key_secret)
        )

    return HTTPFacilitatorClient(FacilitatorConfig(url=settings.facilitator_url))


def build_x402_resource_server(settings: X402Settings) -> x402ResourceServer:
    from x402.mechanisms.evm.exact import ExactEvmServerScheme

    facilitator = build_x402_facilitator_client(settings)
    server = x402ResourceServer(facilitator)
    server.register(settings.network, ExactEvmServerScheme())
    server.register_extension(bazaar_resource_server_extension)
    return server


def _route_resource_url(settings: X402Settings) -> str | None:
    public_base = resolve_public_base_url()
    if not public_base:
        return None
    return public_mcp_url(base_url=public_base, mcp_path=settings.mcp_path)


def build_x402_routes(settings: X402Settings) -> dict[str, RouteConfig]:
    accepts = build_payment_options_for_stables(
        pay_to=settings.pay_to,
        network=settings.network,
        light_price=settings.mcp_price,
        heavy_price=settings.mcp_price_heavy,
        symbols=effective_accepted_stable_symbols(settings.accepted_stables),
    )
    return {
        f"POST {settings.mcp_path}": RouteConfig(
            accepts=accepts,
            resource=_route_resource_url(settings),
            mime_type="application/json",
            description=LISTING_DESCRIPTION,
            extensions=build_http_route_extensions(),
        ),
    }


def cdp_facilitator_configured(env: Mapping[str, str] | None = None) -> bool:
    return load_cdp_api_credentials(env) is not None
