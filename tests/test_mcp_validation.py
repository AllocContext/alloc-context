from __future__ import annotations

import pytest

from alloccontext.mcp.validation import McpValidationError, validate_target_pct, validate_theses
from alloccontext.user_config import load_user_config


def test_validate_target_pct_accepts_arbitrary_symbols() -> None:
    result = validate_target_pct({"BTC": 0.7, "HYPE": 0.1})
    assert result == {"BTC": 0.7, "HYPE": 0.1}


def test_validate_target_pct_does_not_require_sum_to_one() -> None:
    result = validate_target_pct({"BTC": 0.2, "ETH": 0.2})
    assert result["BTC"] == 0.2


def test_validate_target_pct_rejects_empty() -> None:
    with pytest.raises(McpValidationError, match="must not be empty"):
        validate_target_pct({})


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
