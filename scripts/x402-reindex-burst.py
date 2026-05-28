#!/usr/bin/env python3
"""Run one paid call per MCP tool to refresh CDP Bazaar index entries."""

from __future__ import annotations

import os
import subprocess
import sys

TOOLS = (
    "get_market_context",
    "get_context_bundle",
    "get_rebalance_plan",
    "check_allocation_band",
    "get_context_at",
    "get_context_delta",
    "check_allocation_bands",
)


def main() -> None:
    if not os.environ.get("EVM_PRIVATE_KEY", "").strip():
        print("Set EVM_PRIVATE_KEY (buyer wallet, not X402_PAY_TO)", file=sys.stderr)
        sys.exit(1)

    script = os.path.join(os.path.dirname(__file__), "x402-paid-smoke-test.py")
    failures = 0
    for tool in TOOLS:
        print(f"--- {tool} ---")
        env = {**os.environ, "MCP_SMOKE_TOOL": tool}
        result = subprocess.run([sys.executable, script], env=env, check=False)
        if result.returncode != 0:
            failures += 1
    if failures:
        print(f"FAIL: {failures} tool(s) failed", file=sys.stderr)
        sys.exit(1)
    print(f"Re-index burst complete ({len(TOOLS)} tools).")


if __name__ == "__main__":
    main()
