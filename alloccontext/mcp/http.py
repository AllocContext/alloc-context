from __future__ import annotations

import contextlib
import json
import os
from collections.abc import AsyncIterator
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

from alloccontext.mcp.bazaar import (
    build_llms_txt,
    build_mcp_server_card,
    build_well_known_x402,
    resolve_public_base_url,
)
from alloccontext.mcp.glama import build_glama_well_known
from alloccontext.mcp.server import create_server
from alloccontext.mcp.x402_config import (
    CDP_FACILITATOR_URL,
    X402Settings,
    build_x402_resource_server,
    build_x402_routes,
    load_x402_settings,
)
from alloccontext.mcp.x402_stables import effective_accepted_stable_symbols


def _health_verbose_enabled() -> bool:
    return os.environ.get("ALLOC_CONTEXT_HEALTH_VERBOSE", "").lower() in (
        "1",
        "true",
        "yes",
    )


def _health_verbose_allowed(request: Any) -> bool:
    if not _health_verbose_enabled():
        return False
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    return host in ("127.0.0.1", "::1", "localhost")


def _discovery_link_headers() -> dict[str, str]:
    if resolve_public_base_url():
        return {"Link": '</llms.txt>; rel="describedby"'}
    return {}


def _make_health_handler(config_path: str | None) -> Any:
    def _health(request: Any) -> JSONResponse:
        payload: dict[str, Any] = {"ok": True, "service": "alloc-context-mcp"}
        verbose = _health_verbose_allowed(request)
        try:
            from alloccontext.config import load_config
            from alloccontext.store.db import connect
            from alloccontext.status_report import mcp_health_ingest_summary

            config = load_config(config_path)
            conn = connect(config.paths.db)
            try:
                summary = mcp_health_ingest_summary(config, conn)
                payload["ingest_ok"] = summary["ingest_ok"]
                optional_failures = summary.get("optional_feed_failures") or []
                if optional_failures:
                    payload["optional_feed_failures"] = optional_failures
                if verbose:
                    payload["source_health"] = summary.get("source_health")
                    required_failures = summary.get("required_failures") or []
                    if required_failures:
                        payload["required_failures"] = required_failures
            finally:
                conn.close()
        except Exception:
            payload["status_detail"] = "database_unavailable"
            payload["ok"] = False
            payload["ingest_ok"] = False
        return JSONResponse(payload, headers=_discovery_link_headers())

    return _health


def _health(_: Any) -> JSONResponse:
    """Default handler for tests; production apps use _make_health_handler."""
    return _make_health_handler(None)(_)


def _llms_txt(settings: X402Settings) -> PlainTextResponse:
    public_base = resolve_public_base_url()
    if not public_base:
        return PlainTextResponse(
            "Set X402_PUBLIC_URL for discovery metadata.\n",
            status_code=404,
        )
    stables = effective_accepted_stable_symbols(settings.accepted_stables)
    body = build_llms_txt(
        public_url=public_base,
        mcp_path=settings.mcp_path,
        accepted_stables=stables,
    )
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")


def _well_known_x402(settings: X402Settings) -> JSONResponse:
    public_base = resolve_public_base_url()
    if not public_base or not settings.pay_to:
        return JSONResponse({"error": "discovery metadata unavailable"}, status_code=404)
    stables = effective_accepted_stable_symbols(settings.accepted_stables)
    payload = build_well_known_x402(
        public_url=public_base,
        mcp_path=settings.mcp_path,
        pay_to=settings.pay_to,
        price_light=settings.mcp_price,
        price_heavy=settings.mcp_price_heavy,
        network=settings.network,
        accepted_stables=stables,
    )
    return JSONResponse(payload)


def _well_known_mcp_server_card() -> JSONResponse:
    public_base = resolve_public_base_url()
    if not public_base:
        return JSONResponse({"error": "discovery metadata unavailable"}, status_code=404)
    from alloccontext import __version__

    return JSONResponse(build_mcp_server_card(version=__version__))


def _well_known_glama() -> JSONResponse:
    public_base = resolve_public_base_url()
    if not public_base:
        return JSONResponse({"error": "discovery metadata unavailable"}, status_code=404)
    try:
        payload = build_glama_well_known()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    return JSONResponse(payload)


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    return normalized in {"127.0.0.1", "localhost", "::1"}


def _self_host_http_allowed() -> bool:
    """Explicit opt-in for Docker/local HTTP on 0.0.0.0 without x402 (not for public WAN)."""
    return _truthy_env("ALLOC_CONTEXT_SELF_HOST_HTTP")


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def payment_env_configured() -> bool:
    """CDP production facilitator + seller wallet are both set."""
    return (
        os.environ.get("X402_FACILITATOR_URL", "").startswith(CDP_FACILITATOR_URL)
        and bool(os.environ.get("X402_PAY_TO", "").strip())
    )


def _allow_unpaid_http_despite_payment_env() -> bool:
    """Internal MCP (:8001) and Docker self-host may share a payment-capable .env."""
    return _truthy_env("ALLOC_CONTEXT_ALLOW_UNPAID_HTTP") or _self_host_http_allowed()


def resolve_x402_enabled(*, cli_x402: bool = False) -> bool:
    return cli_x402 or _truthy_env("X402_ENABLED")


def enforce_x402_when_payment_env_configured(*, x402: bool) -> None:
    if x402 or not payment_env_configured():
        return
    if _allow_unpaid_http_despite_payment_env():
        return
    raise RuntimeError(
        "CDP payment env is set (CDP facilitator + X402_PAY_TO) but x402 is "
        "disabled. Pass --x402, set X402_ENABLED=1, or set "
        "ALLOC_CONTEXT_ALLOW_UNPAID_HTTP=1 for intentional unpaid loopback "
        "(internal MCP); Docker self-host uses ALLOC_CONTEXT_SELF_HOST_HTTP=1."
    )


def build_http_app(
    *,
    config_path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    stateless_http: bool = True,
    x402: bool = False,
) -> Starlette:
    enforce_x402_when_payment_env_configured(x402=x402)
    if (
        not _is_loopback_host(host)
        and not x402
        and not _self_host_http_allowed()
    ):
        raise RuntimeError(
            "HTTP MCP on a non-loopback host requires x402 payment protection"
        )
    mcp = create_server(
        config_path=config_path,
        host=host,
        port=port,
        stateless_http=stateless_http,
    )
    inner = mcp.streamable_http_app()
    settings = load_x402_settings(require_payment=x402)

    @contextlib.asynccontextmanager
    async def mcp_lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            yield

    discovery_routes = [
        Route("/health", _make_health_handler(config_path)),
        Route("/llms.txt", lambda req: _llms_txt(settings)),
        Route("/.well-known/x402.json", lambda req: _well_known_x402(settings)),
        Route("/.well-known/mcp/server-card.json", lambda req: _well_known_mcp_server_card()),
        Route("/.well-known/glama.json", lambda req: _well_known_glama()),
    ]

    if not settings.enabled:
        return Starlette(
            routes=[
                *discovery_routes,
                Mount("/", app=inner),
            ],
            lifespan=mcp_lifespan,
        )

    from alloccontext.mcp.payment_middleware import AllocContextPaymentMiddlewareASGI

    resource_server = build_x402_resource_server(settings)
    routes = build_x402_routes(settings)
    return Starlette(
        middleware=[
            Middleware(
                AllocContextPaymentMiddlewareASGI,
                routes=routes,
                server=resource_server,
            ),
        ],
        routes=[
            *discovery_routes,
            Mount("/", app=inner),
        ],
        lifespan=mcp_lifespan,
    )


def run_http(
    *,
    config_path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    x402: bool = False,
) -> None:
    import uvicorn

    x402 = resolve_x402_enabled(cli_x402=x402)
    app = build_http_app(
        config_path=config_path,
        host=host,
        port=port,
        x402=x402,
    )
    uvicorn.run(app, host=host, port=port, log_level="info")


async def run_http_async(
    *,
    config_path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    x402: bool = False,
) -> None:
    import uvicorn

    x402 = resolve_x402_enabled(cli_x402=x402)
    app = build_http_app(
        config_path=config_path,
        host=host,
        port=port,
        x402=x402,
    )
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


def _parse_mcp_port(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError as exc:
        raise SystemExit(
            f"ALLOC_CONTEXT_MCP_PORT must be an integer, got {raw!r}"
        ) from exc
    if not 1 <= port <= 65535:
        raise SystemExit(f"ALLOC_CONTEXT_MCP_PORT out of range: {port}")
    return port


def main() -> None:
    host = os.environ.get("ALLOC_CONTEXT_MCP_HOST", "127.0.0.1")
    port = _parse_mcp_port(os.environ.get("ALLOC_CONTEXT_MCP_PORT", "8000"))
    run_http(host=host, port=port, x402=False)


if __name__ == "__main__":
    main()
