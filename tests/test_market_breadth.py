from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from alloccontext.ingest.coingecko import normalize_coingecko_snapshot, refresh_coingecko
from alloccontext.ingest.coinmarketcap import normalize_cmc_snapshot, refresh_coinmarketcap
from alloccontext.ingest.market_snapshots import upsert_crypto_market_snapshot
from alloccontext.rollup.breadth import build_market_breadth_context
from alloccontext.rollup.context import build_context_bundle


def test_normalize_coingecko_snapshot() -> None:
    global_data = json.loads(Path("tests/fixtures/coingecko_global.json").read_text())["data"]
    markets = json.loads(Path("tests/fixtures/coingecko_markets.json").read_text())
    snap = normalize_coingecko_snapshot(global_data=global_data, markets=markets)
    assert snap["btc_rank"] == 1
    assert snap["btc_dominance_pct"] == 62.15
    assert snap["btc_change_pct_24h"] == -1.25


def test_normalize_cmc_snapshot() -> None:
    global_data = json.loads(Path("tests/fixtures/cmc_global.json").read_text())["data"]
    quotes = json.loads(Path("tests/fixtures/cmc_quotes.json").read_text())["data"]
    snap = normalize_cmc_snapshot(global_data=global_data, quotes=quotes)
    assert snap["btc_rank"] == 1
    assert snap["total_market_cap_usd"] == 3245000000000
    assert snap["eth_change_pct_24h"] == -0.9


def test_refresh_coingecko_mock(conn, config, monkeypatch) -> None:
    global_payload = json.loads(Path("tests/fixtures/coingecko_global.json").read_text())
    markets_payload = json.loads(Path("tests/fixtures/coingecko_markets.json").read_text())

    def fake_fetch(url, *, headers=None, timeout=20.0):
        if url.endswith("/global"):
            return global_payload
        if "/coins/markets" in url:
            return markets_payload
        raise AssertionError(url)

    monkeypatch.setattr("alloccontext.ingest.coingecko._fetch_json", fake_fetch)
    result = refresh_coingecko(conn, config)
    assert result["ok"] is True
    assert result["btc_rank"] == 1


def test_refresh_coinmarketcap_skips_without_key(conn, config, monkeypatch) -> None:
    monkeypatch.delenv("COINMARKETCAP_API_KEY", raising=False)
    result = refresh_coinmarketcap(conn, config)
    assert result["skipped"] is True
    assert result["rows"] == 0


def test_refresh_coinmarketcap_skips_on_auth_error(conn, config, monkeypatch) -> None:
    monkeypatch.setenv("COINMARKETCAP_API_KEY", "bad-key")

    def fake_fetch(url, *, api_key, timeout):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr("alloccontext.ingest.coinmarketcap._fetch_json", fake_fetch)
    result = refresh_coinmarketcap(conn, config)
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "coinmarketcap_auth_failed"


def test_refresh_coingecko_falls_back_keyless_on_auth_error(conn, config, monkeypatch) -> None:
    global_payload = json.loads(Path("tests/fixtures/coingecko_global.json").read_text())
    markets_payload = json.loads(Path("tests/fixtures/coingecko_markets.json").read_text())
    calls: list[str | None] = []

    def fake_fetch(url, *, headers=None, timeout=20.0):
        key = (headers or {}).get("x-cg-demo-api-key")
        calls.append(key)
        if key == "bad-key":
            raise urllib.error.HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)
        if url.endswith("/global"):
            return global_payload
        if "/coins/markets" in url:
            return markets_payload
        raise AssertionError(url)

    monkeypatch.setenv("COINGECKO_API_KEY", "bad-key")
    monkeypatch.setattr("alloccontext.ingest.coingecko._fetch_json", fake_fetch)
    result = refresh_coingecko(conn, config)
    assert result["ok"] is True
    assert result["btc_rank"] == 1
    assert calls[0] == "bad-key"
    assert calls[1] is None


def test_refresh_coingecko_skips_when_keyless_auth_fails(conn, config, monkeypatch) -> None:
    def fake_fetch(url, *, headers=None, timeout=20.0):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)

    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    monkeypatch.setattr("alloccontext.ingest.coingecko._fetch_json", fake_fetch)
    result = refresh_coingecko(conn, config)
    assert result["ok"] is True
    assert result["skipped"] is True


def test_refresh_coingecko_skips_on_rate_limit(conn, config, monkeypatch) -> None:
    def fake_fetch(url, *, headers=None, timeout=20.0):
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", hdrs=None, fp=None)

    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    monkeypatch.setattr("alloccontext.ingest.coingecko._fetch_json", fake_fetch)
    result = refresh_coingecko(conn, config)
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "coingecko_rate_limited"


def test_refresh_coinmarketcap_skips_on_rate_limit(conn, config, monkeypatch) -> None:
    monkeypatch.setenv("COINMARKETCAP_API_KEY", "test-key")

    def fake_fetch(url, *, api_key, timeout):
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", hdrs=None, fp=None)

    monkeypatch.setattr("alloccontext.ingest.coinmarketcap._fetch_json", fake_fetch)
    result = refresh_coinmarketcap(conn, config)
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "coinmarketcap_rate_limited"


def test_refresh_coinmarketcap_mock(conn, config, monkeypatch) -> None:
    global_payload = json.loads(Path("tests/fixtures/cmc_global.json").read_text())
    quotes_payload = json.loads(Path("tests/fixtures/cmc_quotes.json").read_text())

    def fake_fetch(url, *, api_key, timeout):
        if "global-metrics" in url:
            return global_payload
        if "quotes/latest" in url:
            return quotes_payload
        raise AssertionError(url)

    monkeypatch.setenv("COINMARKETCAP_API_KEY", "test-key")
    monkeypatch.setattr("alloccontext.ingest.coinmarketcap._fetch_json", fake_fetch)
    result = refresh_coinmarketcap(conn, config)
    assert result["ok"] is True
    assert result["btc_dominance_pct"] == 62.1


def test_build_market_breadth_context_with_delta(conn, config) -> None:
    snap = normalize_coingecko_snapshot(
        global_data=json.loads(Path("tests/fixtures/coingecko_global.json").read_text())["data"],
        markets=json.loads(Path("tests/fixtures/coingecko_markets.json").read_text()),
    )
    prior = dict(snap)
    prior["btc_dominance_pct"] = 61.5
    upsert_crypto_market_snapshot(
        conn, source="coingecko", snapshot_ts="2026-05-20T12:00:00+00:00", snapshot=prior
    )
    upsert_crypto_market_snapshot(
        conn, source="coingecko", snapshot_ts="2026-05-21T12:00:00+00:00", snapshot=snap
    )
    ctx = build_market_breadth_context(conn)
    assert ctx["available"] is True
    cg = ctx["feeds"]["coingecko"]
    assert cg["btc_dominance_pct"] == 62.15
    assert cg["delta_since_prior"]["btc_dominance_change"] == 0.65


def test_context_bundle_includes_market_breadth(conn, config) -> None:
    snap = normalize_coingecko_snapshot(
        global_data=json.loads(Path("tests/fixtures/coingecko_global.json").read_text())["data"],
        markets=json.loads(Path("tests/fixtures/coingecko_markets.json").read_text()),
    )
    upsert_crypto_market_snapshot(
        conn,
        source="coingecko",
        snapshot_ts=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc).isoformat(),
        snapshot=snap,
    )
    bundle = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        as_of=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
    )
    assert bundle["market"]["available"] is True
    assert bundle["market"]["breadth"]["feeds"]["coingecko"]["available"] is True
