from __future__ import annotations

import json

from alloccontext.mcp.handlers import get_context_bundle
from alloccontext.rollup.context import build_context_bundle
from alloccontext.rollup.regime_history import (
    DEFAULT_REGIME_HORIZON_DAYS,
    attach_regime_history,
    build_regime_history_comparison,
    derive_regime_posture,
)


def _risk_off(score: int, level: str) -> dict:
    return {"available": True, "score": score, "level": level, "signals": []}


def _bundle(
    *,
    as_of: str,
    fg: int | None = None,
    risk_score: int = 20,
    risk_level: str = "low",
    btc_price: float = 100_000.0,
) -> dict:
    sentiment = {"available": fg is not None, "fear_greed": {"value": fg, "classification": "Neutral"}}
    if fg is None:
        sentiment = {"available": False}
    return {
        "scope": "daily",
        "as_of": as_of,
        "portfolio": {"available": True, "nav_usd": 10_000.0, "allocation_pct": {"BTC": 0.8, "CASH": 0.2}},
        "market": {
            "available": True,
            "assets": {"btc": {"price_usd": btc_price}},
        },
        "sentiment": sentiment,
        "regime": {"available": True, "risk_off": _risk_off(risk_score, risk_level), "hints": []},
        "delta": {"available": True, "notable_shifts": []},
    }


def test_derive_regime_posture_risk_off_high() -> None:
    current = _bundle(as_of="2026-06-09T12:00:00+00:00", risk_score=75, risk_level="high")
    posture = derive_regime_posture(current, horizon_7d=None)
    assert posture["label"] == "RISK_OFF"
    assert posture["trajectory"] == "UNKNOWN"


def test_derive_regime_posture_trajectory_deteriorating() -> None:
    current = _bundle(as_of="2026-06-09T12:00:00+00:00", risk_score=55, risk_level="moderate")
    horizon = {
        "days": 7,
        "available": True,
        "risk_off": {"score_then": 20, "score_now": 55, "score_delta": 35},
    }
    posture = derive_regime_posture(current, horizon_7d=horizon)
    assert posture["label"] == "NEUTRAL"
    assert posture["trajectory"] == "DETERIORATING"
    assert posture["basis_days"] == 7


def test_build_regime_history_comparison_with_snapshots(conn, config) -> None:
    baseline = _bundle(
        as_of="2026-06-02T12:00:00+00:00",
        fg=68,
        risk_score=15,
        risk_level="low",
        btc_price=95_000.0,
    )
    current = _bundle(
        as_of="2026-06-09T12:00:00+00:00",
        fg=52,
        risk_score=45,
        risk_level="moderate",
        btc_price=100_000.0,
    )
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        VALUES (?, ?, ?)
        """,
        ("daily", baseline["as_of"], json.dumps(baseline)),
    )
    conn.commit()

    payload = build_regime_history_comparison(conn, scope="daily", current=current)
    history = payload["history"]
    assert len(history) == len(DEFAULT_REGIME_HORIZON_DAYS)
    seven = next(row for row in history if row["days"] == 7)
    assert seven["available"] is True
    assert seven["baseline_as_of"] == baseline["as_of"]
    assert seven["fear_greed"]["change"] == -16
    assert seven["btc_change_pct"] == 5.26
    assert payload["posture"]["trajectory"] == "DETERIORATING"


def test_get_context_bundle_includes_regime_history(conn, config) -> None:
    baseline = _bundle(
        as_of="2026-06-02T12:00:00+00:00",
        fg=70,
        risk_score=10,
        risk_level="low",
        btc_price=90_000.0,
    )
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        VALUES (?, ?, ?)
        """,
        ("daily", baseline["as_of"], json.dumps(baseline)),
    )
    conn.commit()

    bundle = get_context_bundle(conn, config, scope="daily", freshness="cached")
    comparison = bundle["regime"]["comparison"]
    assert "history" in comparison
    assert "posture" in comparison
    assert isinstance(comparison["history"], list)


def test_attach_regime_history_noop_without_regime(conn) -> None:
    bundle = {"as_of": "2026-06-09T12:00:00+00:00"}
    assert attach_regime_history(conn, scope="daily", bundle=bundle) == bundle


def test_build_context_bundle_attaches_history(conn, config) -> None:
    prior = _bundle(as_of="2026-06-01T12:00:00+00:00", fg=60, risk_score=25, risk_level="low")
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        VALUES (?, ?, ?)
        """,
        ("daily", prior["as_of"], json.dumps(prior)),
    )
    conn.commit()

    bundle = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=False,
    )
    comparison = bundle["regime"]["comparison"]
    assert comparison.get("posture", {}).get("available") in {True, False}
    assert len(comparison.get("history") or []) == 2
