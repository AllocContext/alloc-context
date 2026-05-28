"""Shared Python interpreter resolution for alloc-context scripts."""

from __future__ import annotations

import os
import sys


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_python() -> str:
    """Prefer repo .venv; fall back to the current interpreter."""
    venv_python = os.path.join(repo_root(), ".venv", "bin", "python")
    if os.path.isfile(venv_python):
        return venv_python
    return sys.executable


def script_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for subprocess/script runs (repo on PYTHONPATH)."""
    env = dict(os.environ)
    root = repo_root()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root if not existing else f"{root}{os.pathsep}{existing}"
    if extra:
        env.update(extra)
    return env


def ensure_importable() -> None:
    """Allow `from alloccontext...` when run as scripts/foo.py without editable install."""
    root = repo_root()
    if root not in sys.path:
        sys.path.insert(0, root)


def require_hosted_python() -> str:
    """Return interpreter path or exit with setup instructions."""
    python = resolve_python()
    if python == sys.executable and not os.path.isfile(
        os.path.join(repo_root(), ".venv", "bin", "python")
    ):
        print(
            "No .venv found. From alloc-context/: python3 -m venv .venv && "
            "source .venv/bin/activate && pip install -e '.[hosted]'",
            file=sys.stderr,
        )
        sys.exit(1)
    return python
