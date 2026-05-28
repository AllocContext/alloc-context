#!/usr/bin/env python3
"""Pay once against the hosted MCP and call an MCP tool (mainnet smoke test)."""

from __future__ import annotations

import base64
import json
import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _script_runtime import ensure_importable

ensure_importable()

from alloccontext.mcp.bazaar import smoke_tool_arguments
from alloccontext.x402_smoke_redact import redact_evm_addresses, smoke_log

MCP_URL = os.environ.get("MCP_URL", "https://mcp.alloc-context.com/mcp")
TOOL = os.environ.get("MCP_SMOKE_TOOL", "get_market_context")


def _fail(message: str) -> None:
    print(redact_evm_addresses(message), file=sys.stderr)
    sys.exit(1)


def _tool_arguments() -> dict:
    try:
        return smoke_tool_arguments(TOOL)
    except KeyError:
        _fail(f"Unknown MCP_SMOKE_TOOL: {TOOL}")


def _decode_payment_required(response) -> dict | None:
    header = response.headers.get("PAYMENT-REQUIRED") or response.headers.get("payment-required")
    if not header:
        return None
    try:
        return json.loads(base64.b64decode(header))
    except (json.JSONDecodeError, ValueError):
        return None


def _print_payment_required(response) -> None:
    decoded = _decode_payment_required(response)
    if not decoded:
        smoke_log("No PAYMENT-REQUIRED header on response.")
        return
    if decoded.get("error"):
        smoke_log(f"Payment error: {decoded['error']}")
    accepts = decoded.get("accepts") or []
    if accepts:
        option = accepts[0]
        smoke_log(
            "Required: "
            f"{option.get('network')} "
            f"{option.get('amount')} asset "
            f"{option.get('asset')} payTo {option.get('payTo')}"
        )


def _check_tool_text(text: str) -> None:
    if text.startswith("Error executing tool"):
        _fail(text[:800])
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return
    if isinstance(payload, dict) and payload.get("available") is False:
        _fail(json.dumps(payload, indent=2)[:800])


def _tools_call_payload(*, tool: str, arguments: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }


def main() -> None:
    private_key = os.environ.get("EVM_PRIVATE_KEY", "").strip()
    if not private_key:
        _fail("Set EVM_PRIVATE_KEY to your wallet private key (0x... or raw hex)")

    try:
        from eth_account import Account
        from x402 import x402ClientSync
        from x402.http import x402HTTPClientSync
        from x402.http.clients import x402_requests
        from x402.http.clients.requests import PaymentError
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact.register import register_exact_evm_client
    except ImportError as exc:
        _fail(f"Missing dependency: {exc}. Run: pip install 'alloc-context[hosted]' eth-account")

    tool_args = _tool_arguments()
    account = Account.from_key(private_key)
    payer = account.address
    smoke_log(f"Payer wallet: {payer}")
    smoke_log(f"MCP URL: {MCP_URL}")
    smoke_log(f"Tool: {TOOL}")

    import requests as _requests

    preflight_payload = _tools_call_payload(tool=TOOL, arguments=tool_args)
    preflight_payload["id"] = 0
    preflight = _requests.post(
        MCP_URL,
        json=preflight_payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=30,
    )
    preflight_decoded = _decode_payment_required(preflight)
    pay_to = None
    if preflight_decoded:
        pay_to = (preflight_decoded.get("accepts") or [{}])[0].get("payTo")
    if pay_to and pay_to.lower() == payer.lower():
        _fail(
            "Payer matches X402_PAY_TO — CDP returns self_send_not_allowed. "
            "Use a different wallet to pay."
        )
    if pay_to:
        smoke_log(f"Seller payTo: {pay_to}")

    client = x402ClientSync()
    register_exact_evm_client(client, EthAccountSigner(account))
    http_client = x402HTTPClientSync(client)

    payload = _tools_call_payload(tool=TOOL, arguments=tool_args)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        with x402_requests(http_client) as session:
            response = session.post(MCP_URL, json=payload, headers=headers, timeout=120)
    except PaymentError as exc:
        _fail(f"x402 client payment error: {exc}")

    smoke_log(f"HTTP status: {response.status_code}")
    if not response.ok:
        _print_payment_required(response)
        body = response.text.strip()
        if body:
            smoke_log(f"Body: {body[:500]}")
        _fail("Paid request still returned non-200 (see Payment error above)")

    settle = http_client.get_payment_settle_response(lambda name: response.headers.get(name))
    if settle is not None:
        smoke_log(f"Settlement: success={settle.success}")
        if settle.transaction:
            smoke_log(f"Transaction: {settle.transaction}")
        if settle.network:
            smoke_log(f"Network: {settle.network}")

    body = response.json()
    if "error" in body:
        _fail(json.dumps(body["error"], indent=2)[:800])

    result = body.get("result", {})
    if result.get("isError"):
        _fail(json.dumps(result, indent=2)[:800])

    content = result.get("content") or []
    if content and isinstance(content[0], dict) and content[0].get("text"):
        text = content[0]["text"]
        _check_tool_text(text)
        try:
            tool_json = json.loads(text)
            smoke_log("Tool response keys: " + ", ".join(sorted(tool_json.keys())[:8]))
            if "as_of" in tool_json:
                smoke_log(f"as_of: {tool_json['as_of']}")
        except json.JSONDecodeError:
            smoke_log("Tool response (truncated): " + text[:200])
    else:
        smoke_log("Raw result: " + json.dumps(result)[:400])

    smoke_log("Paid MCP smoke test succeeded.")


if __name__ == "__main__":
    main()
