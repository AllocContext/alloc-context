"""LangChain tools for an upstream AllocContext MCP (x402 when remote)."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from alloccontext.mcp.bazaar import mcp_tool_specs
from alloccontext.mcp.upstream import call_upstream_tool
from alloccontext.user_config import (
    UserConfig,
    load_user_config,
    resolve_user_config_path,
)

DEFAULT_HOSTED_TOOLS = (
    "get_market_context",
    "get_context_bundle",
    "get_rebalance_plan",
    "check_allocation_band",
)


def hosted_user_config(*, upstream_url: str) -> UserConfig:
    """Minimal bridge user config for LangChain calls to a configured MCP URL."""
    if not upstream_url.strip():
        raise ValueError("upstream_url is required")
    base = UserConfig.empty()
    return replace(
        base,
        upstream=upstream_url.strip(),
        self_host=False,
    )


def resolve_hosted_user_config(*, upstream_url: str | None = None) -> UserConfig:
    """Bridge config: ``user.yaml`` when present, else explicit ``upstream_url``.

    Loads ``~/.config/alloc-context/user.yaml`` (or ``ALLOC_CONTEXT_USER_CONFIG``)
    so ``x402.payer_private_key_file`` and inline payer keys work like the stdio
    bridge. Exchange blocks in ``user.yaml`` are ignored for upstream tool calls.
    """
    path = resolve_user_config_path()
    if path is None or not path.is_file():
        if not upstream_url:
            raise ValueError(
                "upstream_url is required when no user.yaml is configured"
            )
        return hosted_user_config(upstream_url=upstream_url)

    loaded = load_user_config(path)
    upstream = (upstream_url or loaded.upstream).strip()
    if not upstream:
        raise ValueError(
            "Configure upstream in user.yaml or pass upstream_url explicitly"
        )
    if loaded.self_host:
        return replace(
            hosted_user_config(upstream_url=upstream),
            x402=loaded.x402,
            path=loaded.path,
        )
    return replace(loaded, upstream=upstream, self_host=False)


def _args_model(tool_name: str, input_schema: dict[str, Any]) -> type[Any]:
    from pydantic import Field, create_model

    properties = input_schema.get("properties") or {}
    required = frozenset(input_schema.get("required") or [])
    field_defs: dict[str, Any] = {}
    for key, prop in properties.items():
        description = str(prop.get("description") or "")
        if key in required:
            field_defs[key] = (Any, Field(description=description))
        else:
            field_defs[key] = (Any | None, Field(default=None, description=description))
    model_name = "".join(part.title() for part in tool_name.split("_")) + "Input"
    return create_model(model_name, **field_defs)


def build_hosted_langchain_tools(
    user: UserConfig | None = None,
    *,
    tool_names: tuple[str, ...] | None = None,
    upstream_url: str | None = None,
) -> list[Any]:
    """Return LangChain tools that call an upstream MCP with x402 when required.

    Requires ``langchain-core`` and ``alloc-context[hosted]``. Configure an x402
    payer via ``EVM_PRIVATE_KEY``, ``user.yaml`` (``x402.payer_private_key_file``),
    or pass a ``UserConfig`` explicitly. Set ``upstream_url`` or ``upstream`` in
    ``user.yaml`` to your MCP endpoint.
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:
        raise ImportError(
            "LangChain integration requires langchain-core: pip install langchain-core"
        ) from exc

    user = user or resolve_hosted_user_config(upstream_url=upstream_url)
    selected = frozenset(tool_names or DEFAULT_HOSTED_TOOLS)
    specs = {spec["tool_name"]: spec for spec in mcp_tool_specs()}
    missing = selected - specs.keys()
    if missing:
        raise ValueError(f"Unknown MCP tool(s): {', '.join(sorted(missing))}")

    tools: list[Any] = []
    for name in tool_names or DEFAULT_HOSTED_TOOLS:
        spec = specs[name]

        def _invoke(*, _tool_name: str = name, **kwargs: Any) -> str:
            arguments = {key: value for key, value in kwargs.items() if value is not None}
            payload = call_upstream_tool(user, _tool_name, arguments)
            if payload.get("reason") == "upstream_payment_required":
                message = payload.get("message") or (
                    "Configure an x402 payer wallet to call upstream MCP."
                )
                raise RuntimeError(message)
            return json.dumps(payload, separators=(",", ":"))

        tools.append(
            StructuredTool(
                name=name,
                description=spec["description"],
                func=_invoke,
                args_schema=_args_model(name, spec["input_schema"]),
            )
        )
    return tools
