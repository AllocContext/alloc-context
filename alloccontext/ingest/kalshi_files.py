from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KalshiTacticalSnapshot:
    at: str | None
    tape_summary: str | None
    trend_by_asset_60m: dict[str, float | None]
    trend_by_asset_15m: dict[str, float | None]
    volatility_regime: str | None
    sentiment_up_frac: float | None
    sentiment_sample: int | None
    daily_stats: dict[str, Any]


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_tactical_snapshot(path: Path) -> KalshiTacticalSnapshot | None:
    raw = _read_json(path)
    if not isinstance(raw, dict):
        return None
    cluster = raw.get("cluster") if isinstance(raw.get("cluster"), dict) else {}
    return KalshiTacticalSnapshot(
        at=raw.get("at"),
        tape_summary=raw.get("tape_summary"),
        trend_by_asset_60m=dict(raw.get("trend_by_asset_60m") or {}),
        trend_by_asset_15m=dict(raw.get("trend_by_asset_15m") or {}),
        volatility_regime=raw.get("volatility_regime"),
        sentiment_up_frac=cluster.get("sentiment_up_frac"),
        sentiment_sample=cluster.get("sentiment_sample"),
        daily_stats=dict(raw.get("daily_stats") or {}),
    )
