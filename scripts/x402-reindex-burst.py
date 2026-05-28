#!/usr/bin/env python3
"""Run one paid call per MCP tool to refresh CDP Bazaar index entries."""

from __future__ import annotations

import os
import subprocess
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _script_runtime import repo_root, require_hosted_python, script_env

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

    python = require_hosted_python()
    script = os.path.join(repo_root(), "scripts", "x402-paid-smoke-test.py")
    failures = 0
    for tool in TOOLS:
        print(f"--- {tool} ---")
        env = script_env({"MCP_SMOKE_TOOL": tool})
        result = subprocess.run([python, script], env=env, check=False)
        if result.returncode != 0:
            failures += 1
    if failures:
        print(f"FAIL: {failures} tool(s) failed", file=sys.stderr)
        sys.exit(1)
    print(f"Re-index burst complete ({len(TOOLS)} tools).")


if __name__ == "__main__":
    main()
