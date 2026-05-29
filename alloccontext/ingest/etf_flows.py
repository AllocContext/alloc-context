from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from alloccontext.timeutil import utc_now_iso

SOSO_BASE = "https://openapi.sosovalue.com"
SOSO_HISTORICAL = "/openapi/v2/etf/historicalInflowChart"
SOSO_METRICS = "/openapi/v2/etf/currentEtfDataMetrics"

ETF_PRODUCTS = {
    "BTC": "us-btc-spot",
    "ETH": "us-eth-spot",
}


def _post_json(url: str, body: dict[str, Any], headers: dict[str, str], timeout: float) -> dict:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("invalid JSON object response")
    if parsed.get("code", 0) != 0:
        raise RuntimeError(str(parsed.get("msg") or "sosovalue_api_error"))
    return parsed


def fetch_sosovalue_historical(
    *,
    product: str,
    api_key: str,
    timeout: float,
) -> list[dict[str, Any]]:
    payload = _post_json(
        f"{SOSO_BASE}{SOSO_HISTORICAL}",
        {"type": product},
        {"x-soso-api-key": api_key, "User-Agent": "alloc-context/0.1"},
        timeout,
    )
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        raise ValueError("invalid sosovalue historical payload")
    return [row for row in rows if isinstance(row, dict)]


def fetch_sosovalue_ticker_metrics(
    *,
    product: str,
    api_key: str,
    timeout: float,
) -> list[dict[str, Any]]:
    payload = _post_json(
        f"{SOSO_BASE}{SOSO_METRICS}",
        {"type": product},
        {"x-soso-api-key": api_key, "User-Agent": "alloc-context/0.1"},
        timeout,
    )
    data = payload.get("data") or {}
    rows = data.get("list") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("invalid sosovalue metrics payload")
    return [row for row in rows if isinstance(row, dict)]


def _metric_value(block: Any) -> float | None:
    if not isinstance(block, dict):
        return None
    value = block.get("value")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_date(block: Any) -> str | None:
    if not isinstance(block, dict):
        return None
    raw = block.get("lastUpdateDate") or block.get("date")
    return str(raw)[:10] if raw else None


def load_fallback_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return raw if isinstance(raw, dict) else {}


def upsert_etf_flow_days(
    conn: sqlite3.Connection,
    *,
    asset: str,
    rows: list[dict[str, Any]],
    source: str,
) -> int:
    fetched_at = utc_now_iso()
    count = 0
    for row in rows:
        flow_date = str(row.get("date") or row.get("flow_date") or "")[:10]
        if not flow_date:
            continue
        net_flow = row.get("totalNetInflow", row.get("net_flow_usd"))
        conn.execute(
            """
            INSERT INTO etf_flow_days(
              asset, flow_date, net_flow_usd, total_value_traded_usd,
              total_net_assets_usd, cum_net_inflow_usd, source, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset, flow_date) DO UPDATE SET
              net_flow_usd = excluded.net_flow_usd,
              total_value_traded_usd = excluded.total_value_traded_usd,
              total_net_assets_usd = excluded.total_net_assets_usd,
              cum_net_inflow_usd = excluded.cum_net_inflow_usd,
              source = excluded.source,
              fetched_at = excluded.fetched_at
            """,
            (
                asset,
                flow_date,
                _float_or_none(net_flow),
                _float_or_none(row.get("totalValueTraded", row.get("total_value_traded_usd"))),
                _float_or_none(row.get("totalNetAssets", row.get("total_net_assets_usd"))),
                _float_or_none(row.get("cumNetInflow", row.get("cum_net_inflow_usd"))),
                source,
                fetched_at,
            ),
        )
        count += 1
    return count


def upsert_etf_ticker_flows(
    conn: sqlite3.Connection,
    *,
    asset: str,
    rows: list[dict[str, Any]],
    source: str,
) -> int:
    fetched_at = utc_now_iso()
    count = 0
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        inflow = row.get("dailyNetInflow") if "dailyNetInflow" in row else row.get("net_flow_usd")
        flow_date = _metric_date(inflow) or _metric_date(row.get("netAssets"))
        if not flow_date and isinstance(row.get("flow_date"), str):
            flow_date = row["flow_date"][:10]
        if not flow_date:
            flow_date = datetime.now(timezone.utc).date().isoformat()
        conn.execute(
            """
            INSERT INTO etf_ticker_flows(
              asset, ticker, flow_date, net_flow_usd, net_assets_usd,
              institute, source, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset, ticker, flow_date) DO UPDATE SET
              net_flow_usd = excluded.net_flow_usd,
              net_assets_usd = excluded.net_assets_usd,
              institute = excluded.institute,
              source = excluded.source,
              fetched_at = excluded.fetched_at
            """,
            (
                asset,
                ticker,
                flow_date,
                _metric_value(inflow) if isinstance(inflow, dict) else _float_or_none(inflow),
                _metric_value(row.get("netAssets")),
                str(row.get("institute") or "") or None,
                source,
                fetched_at,
            ),
        )
        count += 1
    return count


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ingest_asset_from_fallback(
    conn: sqlite3.Connection,
    *,
    asset: str,
    snapshot: dict[str, Any],
) -> int:
    daily = snapshot.get("daily") or snapshot.get("history") or []
    tickers = snapshot.get("by_ticker") or snapshot.get("tickers") or []
    count = upsert_etf_flow_days(conn, asset=asset, rows=list(daily), source="fallback")
    count += upsert_etf_ticker_flows(conn, asset=asset, rows=list(tickers), source="fallback")
    return count


def refresh_etf_flows(conn: sqlite3.Connection, config) -> dict[str, Any]:
    etf = config.etf
    assets = [str(a).upper() for a in etf.assets]
    api_key = os.environ.get("SOSOVALUE_API_KEY")
    rows_total = 0
    sources: set[str] = set()
    feed_errors: dict[str, str] = {}

    if api_key and etf.sosovalue_enabled:
        for asset in assets:
            product = ETF_PRODUCTS.get(asset)
            if not product:
                continue
            try:
                history = fetch_sosovalue_historical(
                    product=product,
                    api_key=api_key,
                    timeout=etf.timeout_seconds,
                )
                rows_total += upsert_etf_flow_days(
                    conn, asset=asset, rows=history, source="sosovalue"
                )
                metrics = fetch_sosovalue_ticker_metrics(
                    product=product,
                    api_key=api_key,
                    timeout=etf.timeout_seconds,
                )
                rows_total += upsert_etf_ticker_flows(
                    conn, asset=asset, rows=metrics, source="sosovalue"
                )
                sources.add("sosovalue")
            except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError) as exc:
                feed_errors[f"sosovalue_{asset.lower()}"] = str(exc)

    fallback_path = etf.fallback_snapshot
    if fallback_path and fallback_path.exists():
        snapshot = load_fallback_snapshot(fallback_path)
        for asset in assets:
            block = snapshot.get(asset.lower()) or snapshot.get(asset)
            if isinstance(block, dict):
                rows_total += _ingest_asset_from_fallback(conn, asset=asset, snapshot=block)
                sources.add("fallback")

    if rows_total == 0:
        conn.rollback()
        if not api_key and not (fallback_path and fallback_path.exists()):
            return {
                "ok": True,
                "rows": 0,
                "skipped": True,
                "reason": "no_etf_data_source",
            }
        return {
            "ok": False,
            "rows": 0,
            "sources": sorted(sources),
            "feed_errors": feed_errors,
            "error": "etf_ingest_failed",
        }

    conn.commit()
    return {
        "ok": True,
        "rows": rows_total,
        "sources": sorted(sources),
        "feed_errors": feed_errors,
    }
