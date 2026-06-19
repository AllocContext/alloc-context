"""Input validation for MCP financial tools."""

from __future__ import annotations

from typing import Any

from alloccontext.rollup.expectation_review import V0_CLAIM_TYPES

MAX_TARGET_PCT_SYMBOLS = 20
MAX_ALLOCATION_BAND_SCENARIOS = 32


class McpValidationError(ValueError):
    """Raised when MCP tool inputs fail validation."""


def normalize_allocation_pct(values: dict[str, Any]) -> dict[str, float]:
    if not isinstance(values, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, raw in values.items():
        asset = str(key).strip().upper()
        if not asset:
            continue
        try:
            normalized[asset] = float(raw)
        except (TypeError, ValueError):
            continue
    return normalized


def validate_target_pct(values: dict[str, Any]) -> dict[str, float]:
    if not isinstance(values, dict):
        raise McpValidationError("target_pct must be an object")
    if not values:
        raise McpValidationError("target_pct must not be empty")
    if len(values) > MAX_TARGET_PCT_SYMBOLS:
        raise McpValidationError(
            f"target_pct exceeds maximum of {MAX_TARGET_PCT_SYMBOLS} symbols"
        )
    normalized: dict[str, float] = {}
    for key, raw in values.items():
        asset = str(key).strip().upper()
        if not asset:
            continue
        try:
            pct = float(raw)
        except (TypeError, ValueError) as exc:
            raise McpValidationError(f"target_pct.{asset} must be a number") from exc
        if pct < 0 or pct > 1:
            raise McpValidationError(f"target_pct.{asset} must be between 0 and 1")
        normalized[asset] = pct
    if not normalized:
        raise McpValidationError("target_pct must include at least one symbol")
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
