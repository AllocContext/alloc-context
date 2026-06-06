from __future__ import annotations

import pytest

from alloccontext.mcp.validation import McpValidationError, validate_theses
from alloccontext.user_config import load_user_config


def test_validate_theses_requires_recorded_at() -> None:
    with pytest.raises(McpValidationError, match="recorded_at is required"):
        validate_theses([{"id": "t1", "claims": [{"type": "MARKET_SENTIMENT"}]}])


def test_validate_theses_rejects_unsupported_claim_type() -> None:
    with pytest.raises(McpValidationError, match="unsupported"):
        validate_theses(
            [
                {
                    "id": "t1",
                    "recorded_at": "2026-06-01T00:00:00Z",
                    "claims": [{"type": "MOON_LAMBO"}],
                }
            ]
        )


def test_load_user_config_validates_theses(tmp_path) -> None:
    path = tmp_path / "user.yaml"
    path.write_text(
        """
theses:
  - id: bad
    claims:
      - type: ALLOCATION_FIT
"""
    )
    with pytest.raises(ValueError, match="recorded_at is required"):
        load_user_config(path)
