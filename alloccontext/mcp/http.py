from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

from alloccontext.mcp.bazaar import (
    build_llms_txt,
    build_well_known_x402,
    resolve_public_base_url,
)
from alloccontext.mcp.server import create_server
from alloccontext.mcp.x402_config import (
    CDP_FACILITATOR_URL,
    X402Settings,
    build_x402_resource_server,
    build_x402_routes,
    load_x402_settings,
)


def _health(_: Any) -> JSONResponse:
    payload: dict[str, Any] = {"ok": True, "service": "alloc-context-mcp"}
    try:
        from alloccontext.config import load_config
        from alloccontext.store.db import connect
        from alloccontext.store.status import ingest_status

        config = load_config(None)
        conn = connect(config.paths.db)
        try:
            status = ingest_status(conn)
            payload["source_health"] = status.get("source_health")
            payload["ingest_ok"] = all(
                row.get("ok") for row in (status.get("source_health") or {}).values()
            )
        finally:
            conn.close()
    except OSError:
        payload["status_detail"] = "database_unavailable"
    return JSONResponse(payload)


def _llms_txt(settings: X402Settings) -> PlainTextResponse:
    public_base = resolve_public_base_url()
    if not public_base:
        return PlainTextResponse(
            "Set X402_PUBLIC_URL for discovery metadata.\n",
            status_code=404,
        )
    body = build_llms_txt(public_url=public_base, mcp_path=settings.mcp_path)
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")


def _well_known_x402(settings: X402Settings) -> JSONResponse:
    public_base = resolve_public_base_url()
    if not public_base or not settings.pay_to:
        return JSONResponse({"error": "discovery metadata unavailable"}, status_code=404)
    payload = build_well_known_x402(
        public_url=public_base,
        mcp_path=settings.mcp_path,
        pay_to=settings.pay_to,
        price_light=settings.mcp_price,
        price_heavy=settings.mcp_price_heavy,
        network=settings.network,
    )
    return JSONResponse(payload)


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    return normalized in {"127.0.0.1", "localhost", "::1"}


def build_http_app(
    *,
    config_path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    stateless_http: bool = True,
    x402: bool = False,
) -> Starlette:
    if not _is_loopback_host(host) and not x402:
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
        Route("/health", _health),
        Route("/llms.txt", lambda req: _llms_txt(settings)),
        Route("/.well-known/x402.json", lambda req: _well_known_x402(settings)),
    ]

    if not settings.enabled:
        return Starlette(
            routes=[
                *discovery_routes,
                Mount("/", app=inner),
            ],
            lifespan=mcp_lifespan,
        )

    from x402.http.middleware.fastapi import PaymentMiddlewareASGI

    resource_server = build_x402_resource_server(settings)
    routes = build_x402_routes(settings)
    return Starlette(
        middleware=[
            Middleware(
                PaymentMiddlewareASGI,
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

    app = build_http_app(
        config_path=config_path,
        host=host,
        port=port,
        x402=x402,
    )
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    import os

    host = os.environ.get("ALLOC_CONTEXT_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("ALLOC_CONTEXT_MCP_PORT", "8000"))
    x402 = os.environ.get("X402_ENABLED", "").lower() in ("1", "true", "yes")
    if (
        os.environ.get("X402_FACILITATOR_URL", "").startswith(CDP_FACILITATOR_URL)
        and os.environ.get("X402_PAY_TO", "").strip()
    ):
        x402 = True
    run_http(host=host, port=port, x402=x402)


if __name__ == "__main__":
    main()
