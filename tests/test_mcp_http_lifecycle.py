from __future__ import annotations

import pytest


def test_mcp_initialize_over_http(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from alloccontext.mcp.http import build_http_app

    monkeypatch.setenv("ALLOC_CONTEXT_CONFIG", "config/config.example.yaml")
    app = build_http_app(x402=False, config_path="config/config.example.yaml")

    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.1.0"},
                },
                "id": 1,
            },
            headers={
                "Accept": "application/json",
                "Host": "127.0.0.1:8000",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("result", {}).get("serverInfo", {}).get("name") == "alloc-context"


def test_health_verbose_includes_source_health(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from alloccontext.mcp.http import build_http_app

    monkeypatch.setenv("ALLOC_CONTEXT_CONFIG", "config/config.example.yaml")
    monkeypatch.setenv("ALLOC_CONTEXT_HEALTH_VERBOSE", "1")
    app = build_http_app(x402=False, config_path="config/config.example.yaml")

    with TestClient(app) as client:
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "source_health" in body or "status_detail" in body


def test_health_includes_llms_link_when_public_url_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from alloccontext.mcp.http import build_http_app

    monkeypatch.setenv("ALLOC_CONTEXT_CONFIG", "config/config.example.yaml")
    monkeypatch.setenv("X402_PUBLIC_URL", "https://mcp.example.com")
    app = build_http_app(x402=False, config_path="config/config.example.yaml")

    with TestClient(app) as client:
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.headers.get("link") == '</llms.txt>; rel="describedby"'
