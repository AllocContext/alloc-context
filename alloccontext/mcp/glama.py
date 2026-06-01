"""Glama connector well-known metadata (/.well-known/glama.json)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

GLAMA_CONNECTOR_SCHEMA = "https://glama.ai/mcp/schemas/connector.json"


def _repo_glama_json_path() -> Path:
    # alloccontext/mcp/glama.py -> repo root (glama.json lives beside pyproject.toml)
    return Path(__file__).resolve().parents[2] / "glama.json"


def build_glama_well_known() -> dict[str, Any]:
    """Load glama.json for Glama ownership verification on the hosted domain."""
    path = _repo_glama_json_path()
    if not path.is_file():
        msg = f"glama.json not found at {path}"
        raise FileNotFoundError(msg)

    data = json.loads(path.read_text(encoding="utf-8"))
    maintainers: list[dict[str, str]] = []

    email_override = os.environ.get("GLAMA_MAINTAINER_EMAIL", "").strip()
    if email_override:
        maintainers = [{"email": email_override}]
    else:
        connector_emails = data.get("connector_emails") or []
        for entry in connector_emails:
            if isinstance(entry, str) and "@" in entry:
                maintainers.append({"email": entry})
        if not maintainers:
            raw = data.get("maintainers") or []
            for entry in raw:
                if isinstance(entry, dict) and entry.get("email"):
                    maintainers.append({"email": str(entry["email"])})
                elif isinstance(entry, str) and "@" in entry:
                    maintainers.append({"email": entry})

    if not maintainers:
        msg = "glama.json maintainers must include at least one email"
        raise ValueError(msg)

    return {
        "$schema": GLAMA_CONNECTOR_SCHEMA,
        "maintainers": maintainers,
    }
