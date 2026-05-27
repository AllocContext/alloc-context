#!/usr/bin/env python3
"""Verify x402 production configuration (CDP facilitator + discovery)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def _ok(message: str) -> None:
    print(f"OK: {message}")


def main() -> None:
    public_url = os.environ.get("X402_PUBLIC_URL", "").rstrip("/")
    local_url = os.environ.get("X402_CHECK_LOCAL", "").rstrip("/")
    pay_to = os.environ.get("X402_PAY_TO", "").strip()
    network = os.environ.get("X402_NETWORK", "eip155:84532").strip()
    facilitator = os.environ.get(
        "X402_FACILITATOR_URL",
        "https://x402.org/facilitator",
    ).strip()

    if not public_url:
        _fail("X402_PUBLIC_URL is required")
    if not pay_to:
        _fail("X402_PAY_TO is required")

    _ok(f"public URL {public_url}")
    _ok(f"network {network}")
    _ok(f"facilitator {facilitator}")

    if facilitator.startswith("https://api.cdp.coinbase.com"):
        if not (os.environ.get("CDP_API_KEY_ID") and os.environ.get("CDP_API_KEY_SECRET")):
            _fail("CDP facilitator requires CDP_API_KEY_ID and CDP_API_KEY_SECRET")
        try:
            import httpx
            from cdp.x402 import create_facilitator_config
        except ImportError:
            _fail("cdp-sdk and httpx required for CDP facilitator check")
        cfg = create_facilitator_config()
        headers = cfg["create_headers"]()["supported"]
        with httpx.Client(timeout=30) as client:
            response = client.get(f"{cfg['url']}/supported", headers=headers)
        if response.status_code != 200:
            _fail(f"CDP /supported returned {response.status_code}: {response.text[:200]}")
        _ok("CDP facilitator /supported authenticated")

    for path in ("/health", "/llms.txt", "/.well-known/x402.json"):
        checked = False
        for base in (local_url, public_url):
            if not base:
                continue
            url = f"{base}{path}"
            try:
                with urllib.request.urlopen(url, timeout=20) as response:
                    status = response.status
                    body = response.read()
            except urllib.error.HTTPError as exc:
                if base == local_url:
                    continue
                _fail(f"{path} returned HTTP {exc.code}")
            except urllib.error.URLError:
                if base == local_url:
                    continue
                raise
            else:
                if status != 200:
                    if base == local_url:
                        continue
                    _fail(f"{path} returned HTTP {status}")
                _ok(f"GET {path} -> 200 ({base})")
                checked = True
                break
        if not checked:
            _fail(f"could not reach {path} on local or public URL")

    manifest_base = local_url or public_url
    manifest = json.loads(
        urllib.request.urlopen(f"{manifest_base}/.well-known/x402.json", timeout=20).read()
    )
    if manifest.get("payment", {}).get("payTo") != pay_to:
        _fail("x402.json payTo does not match X402_PAY_TO")

    mcp_base = local_url or public_url
    req = urllib.request.Request(
        f"{mcp_base}/mcp",
        data=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=20)
        _fail("POST /mcp should return 402 without payment")
    except urllib.error.HTTPError as exc:
        if exc.code != 402:
            _fail(f"POST /mcp returned HTTP {exc.code}, expected 402")
        payment_required = exc.headers.get("PAYMENT-REQUIRED") or exc.headers.get(
            "payment-required"
        )
        if not payment_required:
            _fail("POST /mcp 402 missing PAYMENT-REQUIRED header")
        _ok("POST /mcp returns 402 with PAYMENT-REQUIRED")

    print("All production checks passed.")


if __name__ == "__main__":
    main()
