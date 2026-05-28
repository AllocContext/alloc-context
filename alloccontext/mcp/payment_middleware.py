"""AllocContext payment middleware with per-tool Bazaar discovery."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.types import ASGIApp

from alloccontext.mcp.x402_bazaar_dynamic import (
    AllocContextHTTPResourceServer,
    patch_resource_info_for_bazaar,
)
from x402.http.constants import SETTLEMENT_OVERRIDES_HEADER
from x402.http.facilitator_client_base import FacilitatorResponseError
from x402.http.middleware.fastapi import (
    FastAPIAdapter,
    _check_if_bazaar_needed,
    _facilitator_error_response,
    _register_bazaar_extension,
)
from x402.http.types import HTTPRequestContext, HTTPTransportContext, PaywallConfig, RoutesConfig
from x402.schemas.hooks import VerifiedPaymentCancelOptions

if TYPE_CHECKING:
    from x402.http.x402_http_server import PaywallProvider
    from x402.server import x402ResourceServer


def alloc_payment_middleware(
    routes: RoutesConfig,
    server: x402ResourceServer,
    paywall_config: PaywallConfig | None = None,
    paywall_provider: PaywallProvider | None = None,
    sync_facilitator_on_start: bool = True,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Like x402 fastapi payment_middleware but with per-tool Bazaar metadata."""
    patch_resource_info_for_bazaar()
    if _check_if_bazaar_needed(routes):
        _register_bazaar_extension(server)

    http_server = AllocContextHTTPResourceServer(server, routes)
    if paywall_provider:
        http_server.register_paywall_provider(paywall_provider)

    init_done = False
    init_lock = asyncio.Lock()

    async def middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        nonlocal init_done

        adapter = FastAPIAdapter(request)
        context = HTTPRequestContext(
            adapter=adapter,
            path=request.url.path,
            method=request.method,
            payment_header=(
                adapter.get_header("payment-signature") or adapter.get_header("x-payment")
            ),
        )

        if not http_server.requires_payment(context):
            return await call_next(request)

        if sync_facilitator_on_start and not init_done:
            async with init_lock:
                if not init_done:
                    try:
                        http_server.initialize()
                    except FacilitatorResponseError as error:
                        return _facilitator_error_response(error)
                    init_done = True

        try:
            result = await http_server.process_http_request(context, paywall_config)
        except FacilitatorResponseError as error:
            return _facilitator_error_response(error)

        if result.type == "no-payment-required":
            return await call_next(request)

        if result.type == "payment-error":
            response = result.response
            if response is None:
                return JSONResponse(content={"error": "Payment required"}, status_code=402)
            if response.is_html:
                return HTMLResponse(
                    content=response.body,
                    status_code=response.status,
                    headers=response.headers,
                )
            return JSONResponse(
                content=response.body or {},
                status_code=response.status,
                headers=response.headers,
            )

        if result.type == "payment-verified":
            request.state.payment_payload = result.payment_payload
            request.state.payment_requirements = result.payment_requirements
            dispatcher = result.cancellation_dispatcher
            transport_context = HTTPTransportContext(request=context)

            try:
                response = await call_next(request)
            except Exception as error:
                if dispatcher is not None:
                    await dispatcher.cancel(
                        VerifiedPaymentCancelOptions(reason="handler_threw", error=error)
                    )
                raise

            if response.status_code >= 400:
                if dispatcher is not None:
                    await dispatcher.cancel(
                        VerifiedPaymentCancelOptions(
                            reason="handler_failed",
                            response_status=response.status_code,
                        )
                    )
                return response

            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            overrides = http_server._extract_settlement_overrides(dict(response.headers))
            if overrides is not None:
                for key in list(response.headers.keys()):
                    if key.lower() == SETTLEMENT_OVERRIDES_HEADER.lower():
                        del response.headers[key]

            transport_context.response_headers = dict(response.headers)

            try:
                settle_result = await http_server.process_settlement(
                    result.payment_payload,
                    result.payment_requirements,
                    context=context,
                    settlement_overrides=overrides,
                    declared_extensions=result.declared_extensions,
                    transport_context=transport_context,
                )
            except FacilitatorResponseError as error:
                return _facilitator_error_response(error)
            except Exception:
                return JSONResponse(content={}, status_code=402)

            if not settle_result.success:
                resp = settle_result.response
                if resp is None:
                    return JSONResponse(content={}, status_code=402)
                if resp.is_html:
                    return Response(
                        content=resp.body,
                        status_code=resp.status,
                        headers=resp.headers,
                        media_type="text/html",
                    )
                return JSONResponse(
                    content=resp.body or {},
                    status_code=resp.status,
                    headers=resp.headers,
                )

            headers = dict(response.headers)
            headers.update(settle_result.headers)
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

        return await call_next(request)

    return middleware


class AllocContextPaymentMiddlewareASGI(BaseHTTPMiddleware):
    """Starlette middleware with AllocContext Bazaar discovery behavior."""

    def __init__(
        self,
        app: ASGIApp,
        routes: RoutesConfig,
        server: x402ResourceServer,
        paywall_config: PaywallConfig | None = None,
        paywall_provider: PaywallProvider | None = None,
    ) -> None:
        super().__init__(app)
        self._middleware = alloc_payment_middleware(
            routes,
            server,
            paywall_config,
            paywall_provider,
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        return await self._middleware(request, call_next)
