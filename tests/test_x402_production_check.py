from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from alloccontext.x402_production_check import (
    X402CheckConfig,
    X402ProductionCheckError,
    check_discovery_metadata,
    check_discovery_paths,
    check_manifest_pay_to,
    check_mcp_payment_gate,
    load_check_config,
    run_production_checks,
)


def test_load_check_config_requires_public_url() -> None:
    with pytest.raises(X402ProductionCheckError, match="X402_PUBLIC_URL"):
        load_check_config({"X402_PAY_TO": "0xabc"})


def test_load_check_config_requires_pay_to() -> None:
    with pytest.raises(X402ProductionCheckError, match="X402_PAY_TO"):
        load_check_config({"X402_PUBLIC_URL": "https://mcp.example.com"})


def test_load_check_config_reads_cdp_secret_file(tmp_path) -> None:
    pem = tmp_path / "cdp.pem"
    pem.write_text("secret-from-file")
    config = load_check_config(
        {
            "X402_PUBLIC_URL": "https://mcp.example.com",
            "X402_PAY_TO": "0xabc",
            "CDP_API_KEY_ID": "key-id",
            "CDP_API_KEY_SECRET_FILE": str(pem),
        }
    )
    assert config.cdp_api_key_id == "key-id"
    assert config.cdp_api_key_secret == "secret-from-file"


def test_load_check_config_missing_secret_file_raises() -> None:
    with pytest.raises(X402ProductionCheckError, match="CDP_API_KEY_SECRET_FILE not readable"):
        load_check_config(
            {
                "X402_PUBLIC_URL": "https://mcp.example.com",
                "X402_PAY_TO": "0xabc",
                "CDP_API_KEY_ID": "key-id",
                "CDP_API_KEY_SECRET_FILE": "/no/such/cdp.pem",
            }
        )


def test_check_discovery_paths_requires_public(monkeypatch) -> None:
    config = X402CheckConfig(
        public_url="https://mcp.example.com",
        local_url="http://127.0.0.1:8000",
        pay_to="0xabc",
        network="eip155:8453",
        facilitator="https://x402.org/facilitator",
        cdp_api_key_id=None,
        cdp_api_key_secret=None,
    )

    def fake_fetch(url: str, *, timeout: float = 20) -> tuple[int, bytes]:
        if url.startswith("https://mcp.example.com"):
            return 200, b"ok"
        if url.startswith("http://127.0.0.1:8000"):
            return 200, b"ok"
        raise AssertionError(url)

    monkeypatch.setattr(
        "alloccontext.x402_production_check._fetch_ok",
        fake_fetch,
    )
    messages = check_discovery_paths(config)
    assert len(messages) == 8
    public_messages = [message for message in messages if "mcp.example.com" in message]
    local_messages = [message for message in messages if "127.0.0.1:8000" in message]
    assert len(public_messages) == 4
    assert len(local_messages) == 4


def test_check_manifest_pay_to_mismatch(monkeypatch) -> None:
    config = X402CheckConfig(
        public_url="https://mcp.example.com",
        local_url="http://127.0.0.1:8000",
        pay_to="0xexpected",
        network="eip155:8453",
        facilitator="https://x402.org/facilitator",
        cdp_api_key_id=None,
        cdp_api_key_secret=None,
    )
    monkeypatch.setattr(
        "alloccontext.x402_production_check._fetch_ok",
        lambda url, *, timeout=20: (
            200,
            json.dumps({"payment": {"payTo": "0xother"}}).encode(),
        ),
    )
    with pytest.raises(X402ProductionCheckError, match="payTo"):
        check_manifest_pay_to(config)


def test_check_mcp_payment_gate_requires_402(monkeypatch) -> None:
    config = X402CheckConfig(
        public_url="https://mcp.example.com",
        local_url="http://127.0.0.1:8000",
        pay_to="0xabc",
        network="eip155:8453",
        facilitator="https://x402.org/facilitator",
        cdp_api_key_id=None,
        cdp_api_key_secret=None,
    )

    def fake_urlopen(req, timeout=20):  # noqa: ARG001
        return MagicMock()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(X402ProductionCheckError, match="402 without payment"):
        check_mcp_payment_gate(config)


def test_check_discovery_metadata_validates_privacy_and_license(monkeypatch) -> None:
    from alloccontext.mcp.bazaar import build_llms_txt, build_well_known_x402

    config = X402CheckConfig(
        public_url="https://mcp.example.com",
        local_url="http://127.0.0.1:8000",
        pay_to="0xabc",
        network="eip155:8453",
        facilitator="https://x402.org/facilitator",
        cdp_api_key_id=None,
        cdp_api_key_secret=None,
    )
    manifest = build_well_known_x402(
        public_url="https://mcp.example.com",
        mcp_path="/mcp",
        pay_to="0xabc",
    )
    llms = build_llms_txt(public_url="https://mcp.example.com", mcp_path="/mcp")

    def fake_fetch(url: str, *, timeout: float = 20) -> tuple[int, bytes]:
        if url.endswith("/.well-known/x402.json"):
            return 200, json.dumps(manifest).encode()
        if url.endswith("/llms.txt"):
            return 200, llms.encode()
        raise AssertionError(url)

    monkeypatch.setattr(
        "alloccontext.x402_production_check._fetch_ok",
        fake_fetch,
    )
    messages = check_discovery_metadata(config)
    assert any("privacy pillars ok" in message for message in messages)
    assert any("license markers ok" in message for message in messages)


def test_run_production_checks_skips_cdp_when_not_cdp_facilitator(monkeypatch) -> None:
    env = {
        "X402_PUBLIC_URL": "https://mcp.example.com",
        "X402_PAY_TO": "0xabc",
        "X402_FACILITATOR_URL": "https://x402.org/facilitator",
        "X402_CHECK_LOCAL": "http://127.0.0.1:8000",
    }
    monkeypatch.setattr(
        "alloccontext.x402_production_check.check_discovery_paths",
        lambda config: ["GET /health -> 200 (http://127.0.0.1:8000)"],
    )
    monkeypatch.setattr(
        "alloccontext.x402_production_check.check_manifest_pay_to",
        lambda config: None,
    )
    monkeypatch.setattr(
        "alloccontext.x402_production_check.check_discovery_metadata",
        lambda config: ["x402.json title/tags ok"],
    )
    monkeypatch.setattr(
        "alloccontext.x402_production_check.check_mcp_payment_gate",
        lambda config: "POST /mcp returns 402 with PAYMENT-REQUIRED",
    )
    messages = run_production_checks(env)
    assert any("non-CDP" in message for message in messages)
    assert any("402" in message for message in messages)
