"""x402 production verification (CDP facilitator + discovery endpoints)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping


class X402ProductionCheckError(RuntimeError):
    """One or more production checks failed."""


@dataclass(frozen=True)
class X402CheckConfig:
    public_url: str
    local_url: str
    pay_to: str
    network: str
    facilitator: str
    cdp_api_key_id: str | None
    cdp_api_key_secret: str | None


def load_check_config(env: Mapping[str, str] | None = None) -> X402CheckConfig:
    source = env if env is not None else os.environ
    public_url = source.get("X402_PUBLIC_URL", "").rstrip("/")
    if not public_url:
        raise X402ProductionCheckError("X402_PUBLIC_URL is required")
    pay_to = source.get("X402_PAY_TO", "").strip()
    if not pay_to:
        raise X402ProductionCheckError("X402_PAY_TO is required")
    return X402CheckConfig(
        public_url=public_url,
        local_url=source.get("X402_CHECK_LOCAL", "http://127.0.0.1:8000").rstrip("/"),
        pay_to=pay_to,
        network=source.get("X402_NETWORK", "eip155:84532").strip(),
        facilitator=source.get(
            "X402_FACILITATOR_URL",
            "https://x402.org/facilitator",
        ).strip(),
        cdp_api_key_id=source.get("CDP_API_KEY_ID"),
        cdp_api_key_secret=source.get("CDP_API_KEY_SECRET"),
    )


def check_cdp_facilitator(config: X402CheckConfig) -> str:
    if not config.facilitator.startswith("https://api.cdp.coinbase.com"):
        return f"facilitator {config.facilitator} (non-CDP)"
    if not (config.cdp_api_key_id and config.cdp_api_key_secret):
        raise X402ProductionCheckError(
            "CDP facilitator requires CDP_API_KEY_ID and CDP_API_KEY_SECRET"
        )
    try:
        import httpx
        from cdp.x402 import create_facilitator_config
    except ImportError as exc:
        raise X402ProductionCheckError(
            "cdp-sdk and httpx required for CDP facilitator check"
        ) from exc
    cfg = create_facilitator_config()
    headers = cfg["create_headers"]()["supported"]
    with httpx.Client(timeout=30) as client:
        response = client.get(f"{cfg['url']}/supported", headers=headers)
    if response.status_code != 200:
        raise X402ProductionCheckError(
            f"CDP /supported returned {response.status_code}: {response.text[:200]}"
        )
    return "CDP facilitator /supported authenticated"


def _fetch_ok(url: str, *, timeout: float = 20) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read()


def check_discovery_paths(config: X402CheckConfig) -> list[str]:
    messages: list[str] = []
    paths = ("/health", "/llms.txt", "/.well-known/x402.json")
    for path in paths:
        checked = False
        for base in (config.local_url, config.public_url):
            if not base:
                continue
            url = f"{base}{path}"
            try:
                status, _body = _fetch_ok(url)
            except urllib.error.HTTPError as exc:
                if base == config.local_url:
                    continue
                raise X402ProductionCheckError(f"{path} returned HTTP {exc.code}") from exc
            except urllib.error.URLError:
                if base == config.local_url:
                    continue
                raise
            else:
                if status != 200:
                    if base == config.local_url:
                        continue
                    raise X402ProductionCheckError(f"{path} returned HTTP {status}")
                messages.append(f"GET {path} -> 200 ({base})")
                checked = True
                break
        if not checked:
            raise X402ProductionCheckError(
                f"could not reach {path} on local or public URL"
            )
    return messages


def check_manifest_pay_to(config: X402CheckConfig) -> None:
    manifest_base = config.local_url or config.public_url
    _status, body = _fetch_ok(f"{manifest_base}/.well-known/x402.json")
    manifest = json.loads(body)
    if manifest.get("payment", {}).get("payTo") != config.pay_to:
        raise X402ProductionCheckError("x402.json payTo does not match X402_PAY_TO")


def check_discovery_metadata(config: X402CheckConfig) -> list[str]:
    """Assert static discovery copy includes Bazaar title, tags, and keywords."""
    from alloccontext.mcp.bazaar import (
        BAZAAR_INDEX_TAGS,
        BAZAAR_SERVICE_NAME,
        DISCOVERY_KEYWORD_MARKERS,
        SERVICE_NAME,
        SERVICE_TITLE,
    )

    messages: list[str] = []
    manifest_base = config.local_url or config.public_url
    _status, manifest_body = _fetch_ok(f"{manifest_base}/.well-known/x402.json")
    manifest = json.loads(manifest_body)
    if manifest.get("name") != SERVICE_NAME:
        raise X402ProductionCheckError("x402.json name missing or wrong")
    if manifest.get("title") != SERVICE_TITLE:
        raise X402ProductionCheckError("x402.json title missing or wrong")
    manifest_tags = manifest.get("tags") or []
    for tag in BAZAAR_INDEX_TAGS:
        if tag not in manifest_tags:
            raise X402ProductionCheckError(f"x402.json missing tag {tag!r}")
    messages.append(f"x402.json title/tags ok ({len(manifest_tags)} tags)")

    _status, llms_body = _fetch_ok(f"{manifest_base}/llms.txt")
    llms = llms_body.decode("utf-8")
    if BAZAAR_SERVICE_NAME not in llms and SERVICE_TITLE not in llms:
        raise X402ProductionCheckError("llms.txt missing service title")
    for marker in DISCOVERY_KEYWORD_MARKERS:
        if marker not in llms.lower():
            raise X402ProductionCheckError(f"llms.txt missing keyword marker {marker!r}")
    messages.append("llms.txt discovery keywords ok")
    return messages


def check_mcp_payment_gate(config: X402CheckConfig) -> str:
    mcp_base = config.local_url or config.public_url
    req = urllib.request.Request(
        f"{mcp_base}/mcp",
        data=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=20)
        raise X402ProductionCheckError("POST /mcp should return 402 without payment")
    except urllib.error.HTTPError as exc:
        if exc.code != 402:
            raise X402ProductionCheckError(
                f"POST /mcp returned HTTP {exc.code}, expected 402"
            ) from exc
        payment_required = exc.headers.get("PAYMENT-REQUIRED") or exc.headers.get(
            "payment-required"
        )
        if not payment_required:
            raise X402ProductionCheckError("POST /mcp 402 missing PAYMENT-REQUIRED header")
    return "POST /mcp returns 402 with PAYMENT-REQUIRED"


def run_production_checks(env: Mapping[str, str] | None = None) -> list[str]:
    """Run all x402 production checks; return OK messages."""
    config = load_check_config(env)
    messages = [
        f"public URL {config.public_url}",
        f"network {config.network}",
    ]
    messages.append(check_cdp_facilitator(config))
    messages.extend(check_discovery_paths(config))
    check_manifest_pay_to(config)
    messages.extend(check_discovery_metadata(config))
    messages.append(check_mcp_payment_gate(config))
    return messages
