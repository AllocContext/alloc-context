"""LangChain tools for the hosted AllocContext MCP (x402 on Base)."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from alloccontext.mcp.bazaar import OFFICIAL_HOSTED_MCP_URL, mcp_tool_specs
from alloccontext.mcp.upstream import call_upstream_tool
from alloccontext.user_config import DEFAULT_UPSTREAM_URL, UserConfig

DEFAULT_HOSTED_TOOLS = (
    "get_market_context",
    "get_context_bundle",
    "get_rebalance_plan",
    "check_allocation_band",
)


def hosted_user_config(*, upstream_url: str | None = None) -> UserConfig:
    """Minimal bridge user config for hosted-only LangChain calls."""
    base = UserConfig.empty()
    return replace(
        base,
        upstream=upstream_url or DEFAULT_UPSTREAM_URL,
        self_host=False,
    )


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
) -> list[Any]:
    """Return LangChain tools that call the hosted MCP with x402 payment.

    Requires ``langchain-core`` and ``alloc-context[hosted]``. Set
    ``EVM_PRIVATE_KEY`` (or configure ``user.yaml`` x402 payer) before use.
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:
        raise ImportError(
            "LangChain integration requires langchain-core: pip install langchain-core"
        ) from exc

    user = user or hosted_user_config()
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


def official_hosted_mcp_url() -> str:
    return OFFICIAL_HOSTED_MCP_URL
