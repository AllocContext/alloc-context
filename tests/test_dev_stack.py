from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_dev_scripts_exist_and_parse() -> None:
    for name in ("dev-up.sh", "dev-down.sh"):
        path = REPO_ROOT / "scripts" / name
        assert path.is_file()
        subprocess.run(["bash", "-n", str(path)], check=True)
        text = path.read_text(encoding="utf-8")
        assert "dev-mcp.pid" in text


def test_dev_up_forces_alloc_context_config() -> None:
    text = (REPO_ROOT / "scripts" / "dev-up.sh").read_text(encoding="utf-8")
    assert 'export ALLOC_CONTEXT_CONFIG="${CONFIG}"' in text


def test_dev_config_loads() -> None:
    from alloccontext.config import load_config

    config = load_config(REPO_ROOT / "config" / "config.dev.yaml")
    assert config.paths.db == Path("state/dev/alloccontext.db")
    assert config.ingest.sources["kraken"] is False
    assert config.ingest.sources["fear_greed"] is True


def test_health_handler_uses_explicit_config_path(config, conn, monkeypatch) -> None:
    from starlette.testclient import TestClient

    from alloccontext.mcp.http import build_http_app

    seen: list[str | Path | None] = []

    def fake_load_config(path: str | Path | None = None):
        seen.append(path)
        return config

    monkeypatch.setattr("alloccontext.config.load_config", fake_load_config)
    monkeypatch.setenv("ALLOC_CONTEXT_CONFIG", "/other/config.yaml")

    app = build_http_app(
        config_path=str(REPO_ROOT / "config/config.dev.yaml"),
        host="127.0.0.1",
        port=8001,
    )
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert seen and seen[0] == str(REPO_ROOT / "config/config.dev.yaml")


def test_local_dev_doc_exists() -> None:
    doc = REPO_ROOT / "docs" / "local-dev.md"
    assert doc.is_file()
    assert "dev-up.sh" in doc.read_text(encoding="utf-8")
