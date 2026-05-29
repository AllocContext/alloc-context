from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_JSON = REPO_ROOT / "server.json"

# Official MCP Registry limit (see registry validation errors).
REGISTRY_DESCRIPTION_MAX_LEN = 100


def test_server_json_description_within_registry_limit():
    data = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    description = data["description"]
    assert len(description) <= REGISTRY_DESCRIPTION_MAX_LEN, (
        f"server.json description is {len(description)} chars; "
        f"registry max is {REGISTRY_DESCRIPTION_MAX_LEN}"
    )


def test_server_json_version_matches_pyproject():
    import tomllib

    py_ver = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    data = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
    assert data["version"] == py_ver
    assert data["packages"][0]["version"] == py_ver


def test_readme_includes_mcp_registry_name_for_pypi():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "mcp-name: io.github.negillett/alloc-context" in readme
