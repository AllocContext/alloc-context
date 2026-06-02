#!/usr/bin/env python3
"""Call AllocContext hosted MCP tools through LangChain StructuredTools."""

from __future__ import annotations

import json
import sys

from alloccontext.integrations.langchain import build_hosted_langchain_tools
from alloccontext.mcp.bazaar import smoke_tool_arguments


def main() -> None:
    tools = build_hosted_langchain_tools()
    by_name = {tool.name: tool for tool in tools}
    tool_name = "get_market_context"
    if len(sys.argv) > 1:
        tool_name = sys.argv[1]
    tool = by_name.get(tool_name)
    if tool is None:
        print(f"Unknown tool {tool_name!r}. Choose from: {', '.join(by_name)}", file=sys.stderr)
        sys.exit(1)

    try:
        args = smoke_tool_arguments(tool_name)
    except KeyError:
        print(f"No smoke defaults for tool {tool_name!r}", file=sys.stderr)
        sys.exit(1)

    try:
        raw = tool.invoke(args)
    except RuntimeError as exc:
        if "payer" in str(exc).lower() or "x402" in str(exc).lower():
            print(
                "Configure x402 payer: EVM_PRIVATE_KEY, user.yaml "
                "(x402.payer_private_key_file), or see docs/langchain-integration.md",
                file=sys.stderr,
            )
            sys.exit(1)
        raise

    parsed = json.loads(raw)
    print(json.dumps(parsed, indent=2)[:4000])


if __name__ == "__main__":
    main()
