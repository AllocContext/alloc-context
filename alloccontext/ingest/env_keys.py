from __future__ import annotations

import os


def optional_env_key(name: str) -> str | None:
    """Return env value when non-empty after strip; else None."""
    raw = os.environ.get(name)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None
