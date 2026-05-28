"""Dynamic Bazaar metadata for MCP tools/call on POST /mcp."""

from __future__ import annotations

import dataclasses
from contextvars import ContextVar, Token
from typing import Any

from alloccontext.mcp.bazaar import (
    BAZAAR_INDEX_TAGS,
    BAZAAR_SERVICE_NAME,
    LISTING_DESCRIPTION,
    build_http_route_extensions,
    build_mcp_tool_extensions,
    mcp_tool_specs,
)
from alloccontext.mcp.x402_pricing import read_mcp_request_json
from x402.http.types import HTTPRequestContext, RouteConfig
from x402.http.x402_http_server import x402HTTPResourceServer

_mcp_tool_ctx: ContextVar[str | None] = ContextVar("alloc_mcp_bazaar_tool", default=None)
_TOOL_EXTENSIONS = build_mcp_tool_extensions()
_TOOL_DESCRIPTIONS = {spec["tool_name"]: spec["description"] for spec in mcp_tool_specs()}
_RESOURCE_INFO_PATCHED = False


@dataclasses.dataclass(frozen=True)
class BazaarIndexResourceInfo:
    service_name: str
    tags: tuple[str, ...]


def bazaar_index_resource_info() -> BazaarIndexResourceInfo:
    return BazaarIndexResourceInfo(
        service_name=BAZAAR_SERVICE_NAME,
        tags=BAZAAR_INDEX_TAGS,
    )


def mcp_tool_name_from_body(body: dict[str, Any] | None) -> str | None:
    if not body or body.get("method") != "tools/call":
        return None
    params = body.get("params")
    if not isinstance(params, dict):
        return None
    name = params.get("name")
    return name if isinstance(name, str) and name in _TOOL_EXTENSIONS else None


def patch_resource_info_for_bazaar() -> None:
    """Attach CDP service_name/tags to x402 ResourceInfo when unset."""
    global _RESOURCE_INFO_PATCHED
    if _RESOURCE_INFO_PATCHED:
        return
    from x402.schemas.payments import ResourceInfo

    original_init = ResourceInfo.__init__

    def _init_with_bazaar_metadata(self, *args: Any, **kwargs: Any) -> None:
        meta = bazaar_index_resource_info()
        kwargs.setdefault("service_name", meta.service_name)
        kwargs.setdefault("tags", list(meta.tags))
        original_init(self, *args, **kwargs)

    ResourceInfo.__init__ = _init_with_bazaar_metadata  # type: ignore[method-assign]
    _RESOURCE_INFO_PATCHED = True


class AllocContextHTTPResourceServer(x402HTTPResourceServer):
    """Select per-tool Bazaar extensions from tools/call JSON body."""

    async def process_http_request(self, context, paywall_config=None):  # type: ignore[no-untyped-def]
        token: Token[str | None] | None = None
        if context.method == "POST" and context.path.rstrip("/").endswith("/mcp"):
            body = await read_mcp_request_json(context)
            tool_name = mcp_tool_name_from_body(body)
            if tool_name:
                token = _mcp_tool_ctx.set(tool_name)
        try:
            return await super().process_http_request(context, paywall_config)
        finally:
            if token is not None:
                _mcp_tool_ctx.reset(token)

    def _get_route_config(self, path: str, method: str):  # type: ignore[no-untyped-def]
        match = super()._get_route_config(path, method)
        if match is None:
            return match
        route_config, pattern = match
        tool_name = _mcp_tool_ctx.get()
        if not tool_name:
            return match
        tool_extension = _TOOL_EXTENSIONS.get(tool_name)
        if tool_extension is None:
            return match
        description = _TOOL_DESCRIPTIONS.get(tool_name, route_config.description)
        return (
            dataclasses.replace(
                route_config,
                extensions=tool_extension,
                description=description or LISTING_DESCRIPTION,
            ),
            pattern,
        )
