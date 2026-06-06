"""Input validation for MCP financial tools."""

from __future__ import annotations

from typing import Any

from alloccontext.constants import ALLOCATION_ASSETS as _ASSETS
from alloccontext.rollup.expectation_review import V0_CLAIM_TYPES

_PCT_SUM_TOLERANCE = 0.02
MAX_ALLOCATION_BAND_SCENARIOS = 32


class McpValidationError(ValueError):
    """Raised when MCP tool inputs fail validation."""


def validate_target_pct(values: dict[str, Any]) -> dict[str, float]:
    if not isinstance(values, dict):
        raise McpValidationError("target_pct must be an object")
    normalized: dict[str, float] = {}
    for asset in _ASSETS:
        raw = values.get(asset)
        if raw is None:
            normalized[asset] = 0.0
            continue
        try:
            pct = float(raw)
        except (TypeError, ValueError) as exc:
            raise McpValidationError(f"target_pct.{asset} must be a number") from exc
        if pct < 0 or pct > 1:
            raise McpValidationError(f"target_pct.{asset} must be between 0 and 1")
        normalized[asset] = pct
    total = sum(normalized.values())
    if abs(total - 1.0) > _PCT_SUM_TOLERANCE:
        raise McpValidationError(
            f"target_pct must sum to approximately 1 (got {total:.4f})"
        )
    return normalized


def validate_band(band: Any) -> float:
    try:
        value = float(band)
    except (TypeError, ValueError) as exc:
        raise McpValidationError("band must be a number") from exc
    if not 0 < value < 1:
        raise McpValidationError("band must be between 0 and 1 exclusive")
    return value


def validate_theses(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise McpValidationError("theses must be an array")
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise McpValidationError(f"theses[{index}] must be an object")
        thesis_id = str(entry.get("id") or "").strip()
        if not thesis_id:
            raise McpValidationError(f"theses[{index}].id is required")
        recorded_at = str(entry.get("recorded_at") or "").strip()
        if not recorded_at:
            raise McpValidationError(f"theses[{index}].recorded_at is required")
        claims_raw = entry.get("claims")
        if claims_raw is None:
            claims_raw = []
        if not isinstance(claims_raw, list):
            raise McpValidationError(f"theses[{index}].claims must be an array")
        claims: list[dict[str, Any]] = []
        for claim_index, claim in enumerate(claims_raw):
            if not isinstance(claim, dict):
                raise McpValidationError(
                    f"theses[{index}].claims[{claim_index}] must be an object"
                )
            claim_type = str(claim.get("type") or "").strip().upper()
            if not claim_type:
                raise McpValidationError(
                    f"theses[{index}].claims[{claim_index}].type is required"
                )
            if claim_type not in V0_CLAIM_TYPES:
                raise McpValidationError(
                    f"theses[{index}].claims[{claim_index}].type "
                    f"unsupported: {claim_type!r}"
                )
            claims.append(dict(claim))
        thesis: dict[str, Any] = {
            "id": thesis_id,
            "recorded_at": recorded_at,
            "claims": claims,
        }
        if entry.get("asset") is not None:
            thesis["asset"] = str(entry.get("asset"))
        if entry.get("rationale") is not None:
            thesis["rationale"] = entry.get("rationale")
        result.append(thesis)
    return result


def validate_nav_usd(nav_usd: Any) -> float:
    try:
        value = float(nav_usd)
    except (TypeError, ValueError) as exc:
        raise McpValidationError("nav_usd must be a number") from exc
    if value <= 0:
        raise McpValidationError("nav_usd must be positive")
    return value
