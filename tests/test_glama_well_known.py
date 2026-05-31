from __future__ import annotations

import json

import pytest


def test_build_glama_well_known_loads_maintainer_email() -> None:
    from alloccontext.mcp.glama import build_glama_well_known

    payload = build_glama_well_known()
    assert payload["$schema"] == "https://glama.ai/mcp/schemas/connector.json"
    assert payload["maintainers"] == [{"email": "nathangillett@icloud.com"}]


def test_build_glama_well_known_email_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alloccontext.mcp.glama import build_glama_well_known

    monkeypatch.setenv("GLAMA_MAINTAINER_EMAIL", "ops@example.com")
    payload = build_glama_well_known()
    assert payload["maintainers"] == [{"email": "ops@example.com"}]


def test_glama_well_known_route(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from alloccontext.mcp.http import build_http_app

    monkeypatch.setenv("ALLOC_CONTEXT_CONFIG", "config/config.example.yaml")
    monkeypatch.setenv("X402_PUBLIC_URL", "https://mcp.example.com")
    app = build_http_app(x402=False, config_path="config/config.example.yaml")

    with TestClient(app) as client:
        resp = client.get("/.well-known/glama.json")

    assert resp.status_code == 200
    body = resp.json()
    assert body["maintainers"][0]["email"] == "nathangillett@icloud.com"


def test_glama_json_is_valid_connector_schema() -> None:
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "glama.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["$schema"] == "https://glama.ai/mcp/schemas/connector.json"
    assert data["maintainers"][0]["email"]
