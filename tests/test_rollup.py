from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from alloccontext.ingest.kalshi import refresh_kalshi
from alloccontext.rollup.context import build_context_bundle


def _config_with_tactical(config, tactical: Path):
    return replace(
        config,
        kalshi=replace(
            config.kalshi,
            use_api=False,
            fallback_tactical_snapshot=tactical,
            fallback_state=None,
        ),
    )


def test_refresh_kalshi_from_fixture(conn, config, tmp_path: Path) -> None:
    tactical = tmp_path / "tactical_snapshot.json"
    tactical.write_text(Path("tests/fixtures/tactical_snapshot.json").read_text())
    cfg = _config_with_tactical(config, tactical)
    result = refresh_kalshi(conn, cfg)
    assert result["ok"] is True
    assert result["rows"] == 1


def test_build_context_bundle_with_kalshi_and_portfolio(conn, config, tmp_path: Path) -> None:
    tactical = tmp_path / "tactical_snapshot.json"
    tactical.write_text(Path("tests/fixtures/tactical_snapshot.json").read_text())
    cfg = _config_with_tactical(config, tactical)
    refresh_kalshi(conn, cfg)

    conn.execute(
        """
        INSERT INTO portfolio_snapshots(ts, nav_usd, cash_usd, allocation_json, raw_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "2026-05-21T12:00:00+00:00",
            10000.0,
            500.0,
            json.dumps({"BTC": 0.7, "ETH": 0.25, "CASH": 0.05}),
            "{}",
        ),
    )
    conn.execute(
        """
        INSERT INTO fear_greed(ts, value, classification, fetched_at)
        VALUES (?, ?, ?, ?)
        """,
        ("1716300000", 68, "Greed", "2026-05-21T12:00:00+00:00"),
    )
    conn.execute(
        """
        INSERT INTO market_bars(pair, interval_minutes, bar_ts, open, high, low, close)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("XBTUSD", 1440, 1716300000, 90000, 91000, 89000, 90500),
    )
    conn.commit()

    bundle = build_context_bundle(conn, cfg, scope="daily", rollup=cfg.rollup)
    assert bundle["portfolio"]["available"] is True
    assert bundle["market"]["available"] is True
    assert bundle["sentiment"]["available"] is True
    assert bundle["sentiment"]["kalshi"]["available"] is True
    assert bundle["sentiment"]["kalshi"]["tape_summary"]
    assert bundle["sentiment"]["kalshi"]["weighted_drift_5m_pct"] == 0.04
    assert bundle["sentiment"]["fear_greed"]["value"] == 68


def test_rollup_cli_stdout(config, conn, tmp_path: Path, capsys) -> None:
    from alloccontext.__main__ import main

    tactical = tmp_path / "tactical_snapshot.json"
    tactical.write_text(Path("tests/fixtures/tactical_snapshot.json").read_text())
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        Path("config/config.example.yaml")
        .read_text()
        .replace("state/alloccontext.db", str(config.paths.db))
        .replace("use_api: true", "use_api: false")
        .replace("fallback_tactical_snapshot: null", f"fallback_tactical_snapshot: {tactical}")
    )

    code = main(["--config", str(cfg_path), "rollup", "--scope", "daily", "--stdout"])
    assert code == 0
    out = capsys.readouterr().out
    assert "sentiment" in out
    assert "kalshi" in out
