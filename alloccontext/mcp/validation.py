"""Input validation for MCP financial tools."""

from __future__ import annotations

from typing import Any

from alloccontext.constants import ALLOCATION_ASSETS as _ASSETS

_PCT_SUM_TOLERANCE = 0.02


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


def validate_nav_usd(nav_usd: Any) -> float:
    try:
        value = float(nav_usd)
    except (TypeError, ValueError) as exc:
        raise McpValidationError("nav_usd must be a number") from exc
    if value <= 0:
        raise McpValidationError("nav_usd must be positive")
    return value
