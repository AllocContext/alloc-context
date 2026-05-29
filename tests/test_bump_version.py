from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.bump_version import (
    apply_version,
    bump_version,
    check_version,
    parse_version,
    read_current_version,
    resolve_target_version,
    versions_in_sync,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_parse_version_rejects_invalid():
    with pytest.raises(ValueError):
        parse_version("1.0")
    with pytest.raises(ValueError):
        parse_version("v1.0.0")


def test_bump_semver_parts():
    assert bump_version("0.1.0", "patch") == "0.1.1"
    assert bump_version("0.1.9", "minor") == "0.2.0"
    assert bump_version("1.2.3", "major") == "2.0.0"


def test_resolve_target_version_exact_overrides_bump():
    assert (
        resolve_target_version(current="0.1.0", bump="patch", exact="0.5.0")
        == "0.5.0"
    )


def test_resolve_target_version_rejects_downgrade():
    with pytest.raises(ValueError, match="downgrade"):
        resolve_target_version(current="0.2.0", bump=None, exact="0.1.0")


def test_resolve_target_version_rejects_unchanged_exact():
    with pytest.raises(ValueError, match="tag-only"):
        resolve_target_version(current="0.1.0", bump=None, exact="0.1.0")


def test_check_version_passes_when_in_sync(tmp_path: Path):
    for rel in ("pyproject.toml", "server.json", "alloccontext/__init__.py"):
        src = REPO_ROOT / rel
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
    check_version(read_current_version(REPO_ROOT), root=tmp_path)


def test_check_version_fails_when_out_of_sync(tmp_path: Path):
    for rel in ("pyproject.toml", "server.json", "alloccontext/__init__.py"):
        src = REPO_ROOT / rel
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
    with pytest.raises(ValueError, match="out of sync"):
        check_version("9.9.9", root=tmp_path)


def test_apply_version_updates_all_files(tmp_path: Path):
    for rel in ("pyproject.toml", "server.json", "alloccontext/__init__.py"):
        src = REPO_ROOT / rel
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)

    apply_version("9.8.7", root=tmp_path)
    assert read_current_version(tmp_path) == "9.8.7"
    server = json.loads((tmp_path / "server.json").read_text(encoding="utf-8"))
    assert server["version"] == "9.8.7"
    assert server["packages"][0]["version"] == "9.8.7"
    assert versions_in_sync("9.8.7", root=tmp_path)
    check_version("9.8.7", root=tmp_path)
