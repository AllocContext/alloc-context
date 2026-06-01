#!/usr/bin/env python3
"""Validate PyPI release JSON is ready for MCP Registry publish."""

from __future__ import annotations

import json
import sys
from typing import Any


def pypi_release_is_ready(
    payload: dict[str, Any],
    *,
    package: str,
    version: str,
) -> tuple[bool, str]:
    """Return (ready, reason). MCP Registry needs version metadata plus artifacts."""
    info = payload.get("info")
    if not isinstance(info, dict):
        return False, "missing info object"

    indexed_version = info.get("version")
    if indexed_version != version:
        return False, f"info.version is {indexed_version!r}, expected {version!r}"

    indexed_name = info.get("name")
    if indexed_name and indexed_name != package:
        return False, f"info.name is {indexed_name!r}, expected {package!r}"

    urls = payload.get("urls")
    if not isinstance(urls, list) or not urls:
        return False, "urls list is empty"

    packagetypes = {entry.get("packagetype") for entry in urls if isinstance(entry, dict)}
    if "bdist_wheel" not in packagetypes:
        return False, "bdist_wheel artifact not indexed yet"
    if "sdist" not in packagetypes:
        return False, "sdist artifact not indexed yet"

    return True, "ok"


def main() -> int:
    package = sys.argv[1]
    version = sys.argv[2]
    raw = sys.stdin.read()
    if not raw.strip():
        print("empty PyPI JSON response", file=sys.stderr)
        return 1

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid PyPI JSON: {exc}", file=sys.stderr)
        return 1

    ready, reason = pypi_release_is_ready(payload, package=package, version=version)
    if not ready:
        print(reason, file=sys.stderr)
        return 1

    print(f"PyPI release ready: {package}=={version} ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
