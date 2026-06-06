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
    allocation_analysis: dict | None = None,
) -> dict:
    payload = {
        "as_of": as_of,
        "portfolio": _portfolio(symbols=symbols or ["BTC", "ETH"]),
        "market": _market(btc=btc, eth=eth),
        "sentiment": _sentiment(fg=fg, up_frac=up_frac, vol=vol),
        "regime": _regime(level=risk_level, score=risk_score),
    }
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
    current = _bundle(
        as_of="2026-06-02T00:00:00Z",
        btc=100.0,
        allocation_analysis={
            "available": True,
            "outside_band": False,
            "max_drift": 0.02,
            "band": 0.05,
            "drift": {"BTC": 0.02, "ETH": -0.02, "CASH": 0.0},
        },
    )
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
        target_pct={"BTC": 0.5, "ETH": 0.5, "CASH": 0.0},
        band=0.05,
    )
    assert review["claims"][0]["status"] == "supported"


def test_allocation_fit_alt_unsupported() -> None:
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
        target_pct={"BTC": 0.5, "ETH": 0.5, "CASH": 0.0},
        band=0.05,
    )
    assert review["claims"][0]["reason"] == "unsupported_asset"


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
