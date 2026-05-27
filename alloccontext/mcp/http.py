from __future__ import annotations

from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from alloccontext.mcp.server import create_server
from alloccontext.mcp.x402_config import (
    CDP_FACILITATOR_URL,
    build_x402_resource_server,
    build_x402_routes,
    load_x402_settings,
)


def _health(_: Any) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "alloc-context-mcp"})


def build_http_app(
    *,
    config_path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    stateless_http: bool = True,
    x402: bool = False,
) -> Starlette:
    mcp = create_server(
        config_path=config_path,
        host=host,
        port=port,
        stateless_http=stateless_http,
    )
    inner = mcp.streamable_http_app()
    settings = load_x402_settings(require_payment=x402)

    if not settings.enabled:
        return Starlette(
            routes=[
                Route("/health", _health),
                Mount("/", app=inner),
            ],
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
            Route("/health", _health),
            Mount("/", app=inner),
        ],
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
    if os.environ.get("X402_FACILITATOR_URL", "").startswith(CDP_FACILITATOR_URL):
        x402 = True
    run_http(host=host, port=port, x402=x402)


if __name__ == "__main__":
    main()
