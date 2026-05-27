from __future__ import annotations

import pytest

from alloccontext.mcp.handlers import validate_freshness


def test_validate_freshness_cached() -> None:
    assert validate_freshness("cached") == "cached"


def test_validate_freshness_live() -> None:
    assert validate_freshness("live") == "live"


def test_validate_freshness_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="freshness must be"):
        validate_freshness("stale")
