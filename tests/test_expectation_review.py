from __future__ import annotations

from alloccontext.rollup.expectation_review import build_expectation_review


def _market(*, btc: float, eth: float = 3000.0) -> dict:
    return {
        "available": True,
        "assets": {
            "btc": {"price_usd": btc},
            "eth": {"price_usd": eth},
            "zec": {"price_usd": 50.0},
        },
    }


def _portfolio(*, symbols: list[str]) -> dict:
    holdings = [{"symbol": symbol, "weight_pct": 0.5} for symbol in symbols]
    return {"available": True, "holdings": holdings, "allocation_pct": {"BTC": 0.5, "ETH": 0.5, "CASH": 0.0}}


def _sentiment(*, fg: int = 50, up_frac: float = 0.55, vol: str = "medium") -> dict:
    return {
        "available": True,
        "fear_greed": {"value": fg},
        "kalshi": {
            "available": True,
            "volatility_regime": vol,
            "sentiment_up_frac": up_frac,
        },
    }


def _regime(*, level: str = "low", score: int = 10) -> dict:
    return {"risk_off": {"available": True, "level": level, "score": score}}


def _posture(
    *,
    label: str,
    trajectory: str = "UNKNOWN",
    available: bool = True,
    basis_days: int | None = None,
) -> dict:
    return {
        "comparison": {
            "posture": {
                "available": available,
                "label": label,
                "trajectory": trajectory,
                "basis_days": basis_days,
            }
        }
    }


def _bundle(
    *,
    as_of: str,
    btc: float,
    eth: float = 3000.0,
    symbols: list[str] | None = None,
    fg: int = 50,
    vol: str = "medium",
    up_frac: float = 0.55,
    risk_level: str = "low",
    risk_score: int = 10,
    posture: dict | None = None,
    allocation_analysis: dict | None = None,
) -> dict:
    payload = {
        "as_of": as_of,
        "portfolio": _portfolio(symbols=symbols or ["BTC", "ETH"]),
        "market": _market(btc=btc, eth=eth),
        "sentiment": _sentiment(fg=fg, up_frac=up_frac, vol=vol),
        "regime": _regime(level=risk_level, score=risk_score),
    }
    if posture is not None:
        payload["regime"] = {**payload["regime"], **posture}
    if allocation_analysis is not None:
        payload["allocation_analysis"] = allocation_analysis
    return payload


def test_relative_strength_supported() -> None:
    baseline = _bundle(as_of="2026-06-01T00:00:00Z", btc=100.0, symbols=["ZEC", "BTC"])
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=110.0, symbols=["ZEC", "BTC"])
    current["market"]["assets"]["zec"]["price_usd"] = 60.0
    baseline["market"]["assets"]["zec"]["price_usd"] = 50.0

    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [
                    {"type": "RELATIVE_STRENGTH", "asset": "ZEC", "benchmark": "BTC"}
                ],
            }
        ],
    )
    claim = review["claims"][0]
    assert claim["status"] == "supported"
    assert claim["evidence"]["relative_return_pct"] >= 2.0


def test_relative_strength_within_noise_band() -> None:
    baseline = _bundle(as_of="2026-06-01T00:00:00Z", btc=100.0, symbols=["ZEC"])
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=109.8, symbols=["ZEC"])
    baseline["market"]["assets"]["zec"]["price_usd"] = 50.0
    current["market"]["assets"]["zec"]["price_usd"] = 55.0

    review = build_expectation_review(
        baseline_bundles={"zec": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "zec",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [
                    {"type": "RELATIVE_STRENGTH", "asset": "ZEC", "benchmark": "BTC"}
                ],
            }
        ],
    )
    assert review["claims"][0]["status"] == "unknown"
    assert review["claims"][0]["reason"] == "within_noise_band"


def test_relative_strength_missing_baseline() -> None:
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=110.0, symbols=["ZEC"])
    review = build_expectation_review(
        baseline_bundles={"t1": None},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "RELATIVE_STRENGTH", "asset": "ZEC"}],
            }
        ],
    )
    assert review["claims"][0]["status"] == "unknown"
    assert review["claims"][0]["reason"] == "missing_baseline"


def test_allocation_fit_within_band_supported() -> None:
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=100.0)
    review = build_expectation_review(
        baseline_bundles={"t1": current},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "ALLOCATION_FIT", "asset": "BTC"}],
            }
        ],
        target_pct={"BTC": 0.5, "ETH": 0.5},
        band=0.05,
    )
    assert review["claims"][0]["status"] == "supported"
    assert review["claims"][0]["evidence"]["weight_pct"] == 0.5


def test_allocation_fit_alt_missing_quote() -> None:
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=100.0)
    review = build_expectation_review(
        baseline_bundles={"t1": current},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "ALLOCATION_FIT", "asset": "ZEC"}],
            }
        ],
        target_pct={"ZEC": 0.10, "BTC": 0.5, "ETH": 0.5},
        band=0.05,
    )
    assert review["claims"][0]["reason"] == "missing_quote"


def test_allocation_fit_alt_supported() -> None:
    current = _bundle(
        as_of="2026-06-02T00:00:00Z",
        btc=100.0,
        symbols=["ZEC", "BTC"],
    )
    review = build_expectation_review(
        baseline_bundles={"t1": current},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "ALLOCATION_FIT", "asset": "ZEC", "target_pct": 0.5}],
            }
        ],
        band=0.05,
    )
    assert review["claims"][0]["status"] == "supported"


def test_market_sentiment_improving_supported() -> None:
    baseline = _bundle(as_of="2026-06-01T00:00:00Z", btc=100.0, fg=40, up_frac=0.4)
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=100.0, fg=50, up_frac=0.6)
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "MARKET_SENTIMENT", "direction": "IMPROVING"}],
            }
        ],
    )
    assert review["claims"][0]["status"] == "supported"


def test_volatility_regime_decreasing_supported() -> None:
    baseline = _bundle(as_of="2026-06-01T00:00:00Z", btc=100.0, vol="high")
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=100.0, vol="medium")
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "VOLATILITY_REGIME", "direction": "DECREASING"}],
            }
        ],
    )
    assert review["claims"][0]["status"] == "supported"


def test_risk_appetite_increasing_supported() -> None:
    baseline = _bundle(as_of="2026-06-01T00:00:00Z", btc=100.0, risk_level="high", risk_score=80)
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=100.0, risk_level="low", risk_score=20)
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "RISK_APPETITE", "direction": "INCREASING"}],
            }
        ],
    )
    assert review["claims"][0]["status"] == "supported"


def test_regime_expectation_supported() -> None:
    baseline = _bundle(
        as_of="2026-06-01T00:00:00Z",
        btc=100.0,
        posture=_posture(label="NEUTRAL"),
    )
    current = _bundle(
        as_of="2026-06-02T00:00:00Z",
        btc=100.0,
        posture=_posture(label="RISK_ON", trajectory="IMPROVING", basis_days=7),
    )
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "REGIME_EXPECTATION", "posture": "RISK_ON"}],
            }
        ],
    )
    claim = review["claims"][0]
    assert claim["status"] == "supported"
    assert claim["evidence"]["current_posture"] == "RISK_ON"
    assert claim["evidence"]["baseline_posture"] == "NEUTRAL"


def test_regime_expectation_weakened_opposite() -> None:
    baseline = _bundle(
        as_of="2026-06-01T00:00:00Z",
        btc=100.0,
        posture=_posture(label="NEUTRAL"),
    )
    current = _bundle(
        as_of="2026-06-02T00:00:00Z",
        btc=100.0,
        posture=_posture(label="RISK_OFF"),
    )
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "REGIME_EXPECTATION", "posture": "RISK_ON"}],
            }
        ],
    )
    assert review["claims"][0]["status"] == "weakened"


def test_regime_expectation_neutral_within_noise_band() -> None:
    baseline = _bundle(
        as_of="2026-06-01T00:00:00Z",
        btc=100.0,
        posture=_posture(label="RISK_OFF"),
    )
    current = _bundle(
        as_of="2026-06-02T00:00:00Z",
        btc=100.0,
        posture=_posture(label="NEUTRAL"),
    )
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "REGIME_EXPECTATION", "posture": "RISK_ON"}],
            }
        ],
    )
    claim = review["claims"][0]
    assert claim["status"] == "unknown"
    assert claim["reason"] == "within_noise_band"


def test_regime_expectation_invalid_posture() -> None:
    baseline = _bundle(as_of="2026-06-01T00:00:00Z", btc=100.0)
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=100.0)
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "REGIME_EXPECTATION", "posture": "ACCUMULATION"}],
            }
        ],
    )
    assert review["claims"][0]["reason"] == "invalid_posture"


def test_regime_expectation_trajectory_supported() -> None:
    baseline = _bundle(
        as_of="2026-06-01T00:00:00Z",
        btc=100.0,
        posture=_posture(label="NEUTRAL"),
    )
    current = _bundle(
        as_of="2026-06-02T00:00:00Z",
        btc=100.0,
        posture=_posture(label="NEUTRAL", trajectory="STABLE", basis_days=7),
    )
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [
                    {
                        "type": "REGIME_EXPECTATION",
                        "posture": "NEUTRAL",
                        "trajectory": "STABLE",
                    }
                ],
            }
        ],
    )
    assert review["claims"][0]["status"] == "supported"


def test_regime_expectation_trajectory_weakened() -> None:
    baseline = _bundle(
        as_of="2026-06-01T00:00:00Z",
        btc=100.0,
        posture=_posture(label="NEUTRAL"),
    )
    current = _bundle(
        as_of="2026-06-02T00:00:00Z",
        btc=100.0,
        posture=_posture(label="NEUTRAL", trajectory="DETERIORATING", basis_days=7),
    )
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [
                    {
                        "type": "REGIME_EXPECTATION",
                        "posture": "NEUTRAL",
                        "trajectory": "IMPROVING",
                    }
                ],
            }
        ],
    )
    assert review["claims"][0]["status"] == "weakened"


def test_get_context_bundle_attaches_expectation_review(conn, config) -> None:
    import json

    from alloccontext.mcp.handlers import get_context_bundle
    from alloccontext.rollup.context import build_context_bundle

    baseline = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=False,
    )
    baseline["as_of"] = "2026-06-01T12:00:00+00:00"
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        VALUES (?, ?, ?)
        """,
        ("daily", baseline["as_of"], json.dumps(baseline)),
    )
    conn.commit()

    payload = get_context_bundle(
        conn,
        config,
        scope="daily",
        theses=[
            {
                "id": "btc-thesis",
                "recorded_at": baseline["as_of"],
                "claims": [{"type": "MARKET_SENTIMENT", "direction": "IMPROVING"}],
            }
        ],
    )
    review = payload.get("expectation_review") or {}
    assert review.get("available") is True
    assert review.get("claims")


def test_empty_theses_unavailable() -> None:
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=100.0)
    review = build_expectation_review(
        baseline_bundles={},
        current_bundle=current,
        theses=[],
    )
    assert review["available"] is False


def test_price_strength_up_supported() -> None:
    baseline = _bundle(as_of="2026-06-01T00:00:00Z", btc=100.0, symbols=["ZEC"])
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=100.0, symbols=["ZEC"])
    baseline["market"]["assets"]["zec"]["price_usd"] = 50.0
    current["market"]["assets"]["zec"]["price_usd"] = 55.0

    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [
                    {"type": "PRICE_STRENGTH", "asset": "ZEC", "direction": "UP"}
                ],
            }
        ],
    )
    assert review["claims"][0]["status"] == "supported"


def test_price_strength_invalid_direction() -> None:
    baseline = _bundle(as_of="2026-06-01T00:00:00Z", btc=100.0, symbols=["ZEC"])
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=110.0, symbols=["ZEC"])
    baseline["market"]["assets"]["zec"]["price_usd"] = 50.0
    current["market"]["assets"]["zec"]["price_usd"] = 55.0

    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [
                    {"type": "PRICE_STRENGTH", "asset": "ZEC", "direction": "SIDEWAYS"}
                ],
            }
        ],
    )
    assert review["claims"][0]["reason"] == "invalid_direction"


def test_risk_appetite_conflicting_signals_within_noise() -> None:
    baseline = _bundle(
        as_of="2026-06-01T00:00:00Z",
        btc=100.0,
        risk_level="high",
        risk_score=20,
    )
    current = _bundle(
        as_of="2026-06-02T00:00:00Z",
        btc=100.0,
        risk_level="low",
        risk_score=80,
    )
    review = build_expectation_review(
        baseline_bundles={"t1": baseline},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "RISK_APPETITE", "direction": "INCREASING"}],
            }
        ],
    )
    assert review["claims"][0]["reason"] == "within_noise_band"


def test_baseline_as_of_omitted_when_multiple_baselines() -> None:
    baseline_a = _bundle(as_of="2026-06-01T00:00:00Z", btc=100.0)
    baseline_b = _bundle(as_of="2026-05-30T00:00:00Z", btc=90.0)
    current = _bundle(as_of="2026-06-02T00:00:00Z", btc=110.0, fg=60)
    review = build_expectation_review(
        baseline_bundles={"t1": baseline_a, "t2": baseline_b},
        current_bundle=current,
        theses=[
            {
                "id": "t1",
                "recorded_at": "2026-06-01T00:00:00Z",
                "claims": [{"type": "MARKET_SENTIMENT", "direction": "IMPROVING"}],
            },
            {
                "id": "t2",
                "recorded_at": "2026-05-30T00:00:00Z",
                "claims": [{"type": "MARKET_SENTIMENT", "direction": "IMPROVING"}],
            },
        ],
    )
    assert review["baseline_as_of"] is None
    assert review["claims"][0]["evidence"]["baseline_as_of"] == "2026-06-01T00:00:00Z"
    assert review["claims"][1]["evidence"]["baseline_as_of"] == "2026-05-30T00:00:00Z"


def test_allocation_fit_auto_attached_from_config(conn, config) -> None:
    import json

    from alloccontext.mcp.handlers import get_context_bundle
    from alloccontext.rollup.context import build_context_bundle

    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "2026-06-02T12:00:00+00:00",
            10_000.0,
            500.0,
            json.dumps({"BTC": 0.7, "ETH": 0.25, "CASH": 0.05}),
            "{}",
        ),
    )
    baseline = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        save_snapshot=False,
    )
    baseline["as_of"] = "2026-06-01T12:00:00+00:00"
    conn.execute(
        """
        INSERT INTO context_snapshots(scope, as_of, context_json)
        VALUES (?, ?, ?)
        """,
        ("daily", baseline["as_of"], json.dumps(baseline)),
    )
    conn.commit()

    payload = get_context_bundle(
        conn,
        config,
        scope="daily",
        theses=[
            {
                "id": "alloc",
                "recorded_at": baseline["as_of"],
                "claims": [{"type": "ALLOCATION_FIT", "asset": "BTC"}],
            }
        ],
    )
    analysis = payload.get("allocation_analysis") or {}
    assert analysis.get("available") is True
    claim = (payload.get("expectation_review") or {}).get("claims", [])[0]
    assert claim["reason"] != "missing_quote"
