from __future__ import annotations

import os
import sys

import pytest

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
_SCRIPTS_DIR = os.path.abspath(_SCRIPTS_DIR)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _script_runtime import ensure_importable, repo_root, script_env  # noqa: E402


def test_repo_root_points_at_alloc_context() -> None:
    assert os.path.isdir(os.path.join(repo_root(), "alloccontext"))


def test_script_env_prepends_pythonpath() -> None:
    env = script_env()
    assert repo_root() in env["PYTHONPATH"].split(os.pathsep)


def test_ensure_importable_allows_alloccontext_import() -> None:
    ensure_importable()
    import alloccontext  # noqa: F401


def test_reindex_burst_covers_all_mcp_tools() -> None:
    import importlib.util
    import json
    from pathlib import Path

    script = Path(_SCRIPTS_DIR) / "x402-reindex-burst.py"
    spec = importlib.util.spec_from_file_location("x402_reindex_burst", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/mcp/tool_names.json").read_text()
    )
    assert tuple(sorted(module.TOOLS)) == tuple(sorted(fixture))
