from __future__ import annotations

from datetime import datetime, timezone

from alloccontext.horizon import QUARTERLY_DAYS, bars_within_horizon, cutoff_unix
from alloccontext.store.retention import prune_to_horizon


def test_default_horizon_is_quarterly(config) -> None:
    assert config.horizon.days == QUARTERLY_DAYS == 90


def test_bars_within_horizon() -> None:
    now = datetime(2026, 5, 21, tzinfo=timezone.utc)
    floor = cutoff_unix(days=90, now=now)
    bars = [
        {"time": float(floor - 86400), "open": 1, "high": 1, "low": 1, "close": 1},
        {"time": float(floor + 86400), "open": 2, "high": 2, "low": 2, "close": 2},
    ]
    kept = bars_within_horizon(bars, days=90, now=now)
    assert len(kept) == 1
    assert kept[0]["close"] == 2.0


def test_prune_to_horizon(conn, config) -> None:
    old_ts = "2020-01-01T00:00:00+00:00"
    conn.execute(
        "INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd) VALUES (?, ?, ?)",
        (old_ts, 100.0, 10.0),
    )
    conn.execute(
        "INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd) VALUES (?, ?, ?)",
        ("2026-05-21T12:00:00+00:00", 200.0, 20.0),
    )
    conn.commit()
    deleted = prune_to_horizon(conn, config)
    assert deleted["portfolio_snapshots"] >= 1
    remaining = conn.execute("SELECT COUNT(*) AS n FROM portfolio_snapshots").fetchone()
    assert remaining["n"] == 1
