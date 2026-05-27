from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from alloccontext.ingest.etf_flows import refresh_etf_flows
from alloccontext.ingest.macro_calendar import refresh_macro_calendar
from alloccontext.rollup.context import build_context_bundle
from alloccontext.rollup.etf import build_etf_context


def _config_with_etf_fallback(config, fixture: Path):
    return replace(
        config,
        etf=replace(
            config.etf,
            fallback_snapshot=fixture,
            sosovalue_enabled=False,
        ),
    )


def test_refresh_etf_flows_from_fallback(conn, config, tmp_path: Path) -> None:
    fixture = tmp_path / "etf_flows.json"
    fixture.write_text(Path("tests/fixtures/etf_flows.json").read_text())
    cfg = _config_with_etf_fallback(config, fixture)
    result = refresh_etf_flows(conn, cfg)
    assert result["ok"] is True
    assert result["rows"] >= 3
    assert "fallback" in result["sources"]


def test_build_etf_context_weekly(conn, config, tmp_path: Path) -> None:
    fixture = tmp_path / "etf_flows.json"
    fixture.write_text(Path("tests/fixtures/etf_flows.json").read_text())
    cfg = _config_with_etf_fallback(config, fixture)
    refresh_etf_flows(conn, cfg)
    now = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)
    ctx = build_etf_context(conn, now=now, scope="weekly", assets=["BTC", "ETH"])
    assert ctx["available"] is True
    btc = ctx["assets"]["btc"]
    assert btc["net_flow_usd_1d"] == -290.4
    assert btc["by_ticker"]["IBIT"] == 64.1
    eth = ctx["assets"]["eth"]
    assert eth["net_flow_usd_1d"] == 45.2


def test_build_context_bundle_includes_etf(conn, config, tmp_path: Path) -> None:
    fixture = tmp_path / "etf_flows.json"
    fixture.write_text(Path("tests/fixtures/etf_flows.json").read_text())
    cfg = _config_with_etf_fallback(config, fixture)
    refresh_etf_flows(conn, cfg)
    refresh_macro_calendar(conn, cfg)
    now = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    bundle = build_context_bundle(
        conn, cfg, scope="weekly", rollup=cfg.rollup, as_of=now
    )
    assert bundle["macro"]["available"] is True
    assert "etf" in bundle["macro"]
    assert bundle["macro"]["etf"]["btc"]["available"] is True


def test_refresh_etf_flows_sosovalue_mock(conn, config, monkeypatch) -> None:
    hist = json.loads(Path("tests/fixtures/sosovalue_historical_btc.json").read_text())
    metrics = json.loads(Path("tests/fixtures/sosovalue_metrics_btc.json").read_text())

    def fake_post(url, body, headers, timeout):
        if "historicalInflowChart" in url:
            return hist
        if "currentEtfDataMetrics" in url:
            return metrics
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setenv("SOSOVALUE_API_KEY", "test-key")
    cfg = replace(
        config,
        etf=replace(config.etf, assets=["BTC"], sosovalue_enabled=True, fallback_snapshot=None),
    )
    monkeypatch.setattr("alloccontext.ingest.etf_flows._post_json", fake_post)
    result = refresh_etf_flows(conn, cfg)
    assert result["ok"] is True
    assert "sosovalue" in result["sources"]
