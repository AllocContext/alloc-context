#!/usr/bin/env python3
"""Pay once against the hosted MCP and call get_market_context (mainnet smoke test)."""

from __future__ import annotations

import base64
import json
import os
import sys

MCP_URL = os.environ.get("MCP_URL", "https://mcp.alloc-context.com/mcp")
TOOL = os.environ.get("MCP_SMOKE_TOOL", "get_market_context")


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


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
        print("No PAYMENT-REQUIRED header on response.")
        return
    if decoded.get("error"):
        print(f"Payment error: {decoded['error']}")
    accepts = decoded.get("accepts") or []
    if accepts:
        option = accepts[0]
        print(
            "Required:",
            option.get("network"),
            option.get("amount"),
            "asset",
            option.get("asset"),
            "payTo",
            option.get("payTo"),
        )


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

    account = Account.from_key(private_key)
    payer = account.address
    print(f"Payer wallet: {payer}")
    print(f"MCP URL: {MCP_URL}")

    import requests as _requests

    preflight = _requests.post(
        MCP_URL,
        json={
            "jsonrpc": "2.0",
            "id": 0,
            "method": "tools/call",
            "params": {
                "name": TOOL,
                "arguments": {"scope": "daily", "freshness": "cached"},
            },
        },
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
        print(f"Seller payTo: {pay_to}")

    client = x402ClientSync()
    register_exact_evm_client(client, EthAccountSigner(account))
    http_client = x402HTTPClientSync(client)

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": TOOL,
            "arguments": {"scope": "daily", "freshness": "cached"},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        with x402_requests(http_client) as session:
            response = session.post(MCP_URL, json=payload, headers=headers, timeout=120)
    except PaymentError as exc:
        _fail(f"x402 client payment error: {exc}")

    print(f"HTTP status: {response.status_code}")
    if not response.ok:
        _print_payment_required(response)
        body = response.text.strip()
        if body:
            print(f"Body: {body[:500]}")
        _fail("Paid request still returned non-200 (see Payment error above)")

    settle = http_client.get_payment_settle_response(lambda name: response.headers.get(name))
    if settle is not None:
        print(f"Settlement: success={settle.success}")
        if settle.transaction:
            print(f"Transaction: {settle.transaction}")
        if settle.network:
            print(f"Network: {settle.network}")

    body = response.json()
    if "error" in body:
        _fail(json.dumps(body["error"], indent=2)[:800])

    result = body.get("result", {})
    content = result.get("content") or []
    if content and isinstance(content[0], dict) and content[0].get("text"):
        try:
            tool_json = json.loads(content[0]["text"])
            print("Tool response keys:", ", ".join(sorted(tool_json.keys())[:8]))
            if "as_of" in tool_json:
                print(f"as_of: {tool_json['as_of']}")
        except json.JSONDecodeError:
            print("Tool response (truncated):", content[0]["text"][:200])
    else:
        print("Raw result:", json.dumps(result)[:400])

    print("Paid MCP smoke test succeeded.")


if __name__ == "__main__":
    main()
