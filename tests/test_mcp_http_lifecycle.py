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
