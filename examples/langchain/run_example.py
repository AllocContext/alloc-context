#!/usr/bin/env python3
"""Call AllocContext hosted MCP tools through LangChain StructuredTools."""

from __future__ import annotations

import json
import sys

from alloccontext.integrations.langchain import build_hosted_langchain_tools


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

    payload = tool.invoke(
        {
            "scope": "daily",
            "freshness": "cached",
            "assets": ["BTC", "ETH"],
        }
        if tool_name in {"get_market_context", "get_context_bundle"}
        else {}
    )
    parsed = json.loads(payload)
    if parsed.get("reason") == "upstream_payment_required":
        print(
            "Configure x402 payer: export EVM_PRIVATE_KEY=0x... "
            "(see docs/langchain-integration.md)",
            file=sys.stderr,
        )
        sys.exit(1)
    print(json.dumps(parsed, indent=2)[:4000])


if __name__ == "__main__":
    main()
