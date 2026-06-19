#!/usr/bin/env python3
"""Run one paid call per MCP tool to refresh CDP Bazaar index entries."""

from __future__ import annotations

import os
import subprocess
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _script_runtime import ensure_importable, repo_root, require_hosted_python, script_env

ensure_importable()

from alloccontext.mcp.payer import PayerKeyError, resolve_payer_private_key_from_config
from alloccontext.user_config import X402PayerConfig

DEFAULT_PAYER_KEY_FILE = os.path.expanduser("~/.config/alloc-context/x402-payer.key")

TOOLS = (
    "get_market_context",
    "get_context_bundle",
    "get_expectation_review",
    "get_portfolio_state",
    "get_rebalance_plan",
    "check_allocation_band",
    "get_context_at",
    "get_context_delta",
    "check_allocation_bands",
)


def _resolve_payer_key() -> str:
    env_key = os.environ.get("EVM_PRIVATE_KEY", "").strip()
    if env_key:
        return env_key if env_key.startswith("0x") else f"0x{env_key}"

    try:
        key = resolve_payer_private_key_from_config(
            X402PayerConfig(payer_private_key_file=DEFAULT_PAYER_KEY_FILE)
        )
    except PayerKeyError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    if not key:
        print(
            f"Set EVM_PRIVATE_KEY or create {DEFAULT_PAYER_KEY_FILE} "
            "(buyer wallet, not X402_PAY_TO)",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def main() -> None:
    payer_key = _resolve_payer_key()

    python = require_hosted_python()
    script = os.path.join(repo_root(), "scripts", "x402-paid-smoke-test.py")
    failures = 0
    for tool in TOOLS:
        print(f"--- {tool} ---")
        env = script_env(
            {
                "MCP_SMOKE_TOOL": tool,
                "EVM_PRIVATE_KEY": payer_key,
                "MCP_SMOKE_REINDEX": "1",
            }
        )
        result = subprocess.run([python, script], env=env, check=False)
        if result.returncode != 0:
            failures += 1
    if failures:
        print(f"FAIL: {failures} tool(s) failed", file=sys.stderr)
        sys.exit(1)
    print(f"Re-index burst complete ({len(TOOLS)} tools).")


if __name__ == "__main__":
    main()
