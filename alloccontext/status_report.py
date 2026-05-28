from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any

import requests

from alloccontext.config import AppConfig
from alloccontext.mcp.staleness import age_seconds, parse_as_of
from alloccontext.store.db import SCHEMA_VERSION
from alloccontext.store.status import ingest_status
from alloccontext.timeutil import utc_now


def default_mcp_health_url() -> str:
    explicit = os.environ.get("ALLOC_CONTEXT_HEALTH_URL", "").strip()
    if explicit:
        return explicit
    host = os.environ.get("ALLOC_CONTEXT_MCP_HEALTH_HOST", "127.0.0.1").strip()
    port = os.environ.get("ALLOC_CONTEXT_MCP_PORT", "8000").strip()
    return f"http://{host}:{port}/health"


def _age_from_iso(ts: str | None, *, now: datetime | None = None) -> int | None:
    if not ts:
        return None
    try:
        return age_seconds(parse_as_of(str(ts)), now=now)
    except (TypeError, ValueError):
        return None


def format_age(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86_400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86_400}d ago"


def probe_mcp_health(url: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=timeout_seconds)
        detail: dict[str, Any] = {
            "url": url,
            "reachable": True,
            "http_status": response.status_code,
            "ok": response.status_code == 200,
        }
        if response.status_code != 200:
            detail["error"] = response.text[:200]
            return detail
        try:
            body = response.json()
        except json.JSONDecodeError:
            detail["ok"] = False
            detail["error"] = "response was not JSON"
            return detail
        if not isinstance(body, dict):
            detail["ok"] = False
            detail["error"] = "response was not a JSON object"
            return detail
        detail["service_ok"] = bool(body.get("ok"))
        detail["ingest_ok"] = body.get("ingest_ok")
        detail["source_health"] = body.get("source_health")
        detail["status_detail"] = body.get("status_detail")
        if not detail["service_ok"]:
            detail["ok"] = False
        return detail
    except requests.RequestException as exc:
        return {
            "url": url,
            "reachable": False,
            "ok": False,
            "error": str(exc),
        }


def _classify_sources(
    config: AppConfig,
    last_by_source: dict[str, dict[str, Any]],
    *,
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    optional = config.ingest.optional_sources
    required: list[dict[str, Any]] = []
    optional_rows: list[dict[str, Any]] = []

    def row_for(name: str, ingest_row: dict[str, Any] | None) -> dict[str, Any]:
        if ingest_row is None:
            return {
                "source": name,
                "ok": False,
                "never_run": True,
                "finished_at": None,
                "age_seconds": None,
                "rows_upserted": None,
                "error": "no ingest run recorded",
            }
        finished_at = ingest_row.get("finished_at")
        age = _age_from_iso(finished_at, now=now)
        error = ingest_row.get("error")
        return {
            "source": name,
            "ok": error is None,
            "never_run": False,
            "finished_at": finished_at,
            "age_seconds": age,
            "rows_upserted": ingest_row.get("rows_upserted"),
            "error": error,
        }

    for name, enabled in sorted(config.ingest.sources.items()):
        if not enabled:
            continue
        entry = row_for(name, last_by_source.get(name))
        if name in optional:
            optional_rows.append(entry)
        else:
            required.append(entry)

    enabled_names = {n for n, e in config.ingest.sources.items() if e}
    for name, ingest_row in sorted(last_by_source.items()):
        if name in enabled_names:
            continue
        if name not in optional:
            continue
        optional_rows.append(row_for(name, ingest_row))

    return required, optional_rows


def build_status_report(
    config: AppConfig,
    conn: sqlite3.Connection,
    *,
    probe_mcp: bool = True,
    mcp_health_url: str | None = None,
    mcp_timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    now = utc_now()
    snapshot = ingest_status(conn, now=now)
    last_by_source = snapshot.get("last_ingest_by_source") or {}
    required, optional_rows = _classify_sources(config, last_by_source, now=now)

    context_rows = conn.execute(
        """
        SELECT scope, as_of FROM context_snapshots
        ORDER BY scope, as_of DESC
        """
    ).fetchall()
    latest_by_scope: dict[str, str] = {}
    for row in context_rows:
        scope = str(row["scope"])
        if scope not in latest_by_scope:
            latest_by_scope[scope] = str(row["as_of"])

    context_snapshots = [
        {
            "scope": scope,
            "as_of": as_of,
            "age_seconds": _age_from_iso(as_of, now=now),
        }
        for scope, as_of in sorted(latest_by_scope.items())
    ]

    portfolio = snapshot.get("portfolio_latest")
    portfolio_freshness: dict[str, Any] | None = None
    if portfolio and portfolio.get("ts"):
        ts = str(portfolio["ts"])
        portfolio_freshness = {
            "ts": ts,
            "age_seconds": _age_from_iso(ts, now=now),
            "nav_usd": portfolio.get("nav_usd"),
        }

    required_failures = [r["source"] for r in required if not r["ok"]]
    optional_failures = [r["source"] for r in optional_rows if not r["ok"]]
    ingest_ok = not required_failures

    mcp: dict[str, Any] | None = None
    if probe_mcp:
        url = (mcp_health_url or default_mcp_health_url()).strip()
        mcp = probe_mcp_health(url, timeout_seconds=mcp_timeout_seconds)

    summary_ok = ingest_ok and (mcp is None or mcp.get("ok"))

    return {
        "ok": summary_ok,
        "db": str(config.paths.db),
        "schema_version": SCHEMA_VERSION,
        "horizon_days": config.horizon.days,
        "ingest_sources_enabled": config.ingest.sources,
        "ingest_ok": ingest_ok,
        "required_failures": required_failures,
        "optional_failures": optional_failures,
        "ingest": {"required": required, "optional": optional_rows},
        "context_snapshots": context_snapshots,
        "portfolio_snapshot": portfolio_freshness,
        "fear_greed_latest": snapshot.get("fear_greed_latest"),
        "market_bars": snapshot.get("market_bars"),
        "source_health": snapshot.get("source_health"),
        "last_ingest_by_source": last_by_source,
        "recent_ingest": snapshot.get("recent_ingest"),
        "mcp_health": mcp,
        "summary": {
            "ok": summary_ok,
            "ingest_ok": ingest_ok,
            "mcp_ok": mcp.get("ok") if mcp else None,
        },
    }


def _format_ingest_section(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [title]
    if not rows:
        lines.append("  (none)")
        return lines
    for row in rows:
        name = row["source"]
        if row.get("never_run"):
            lines.append(f"  {name:<16} NEVER RUN")
            continue
        status = "ok" if row.get("ok") else "FAIL"
        age = format_age(row.get("age_seconds"))
        rows_n = row.get("rows_upserted")
        extra = f"  rows={rows_n}" if rows_n is not None else ""
        line = f"  {name:<16} {status:<4} {age}{extra}"
        if not row.get("ok") and row.get("error"):
            err = str(row["error"])[:80]
            line = f"{line}  ({err})"
        lines.append(line)
    return lines


def format_status_report(report: dict[str, Any]) -> str:
    lines = ["AllocContext status", f"DB: {report['db']} (schema v{report['schema_version']})"]
    lines.append(f"Horizon: {report['horizon_days']} days")
    lines.append("")

    ingest = report.get("ingest") or {}
    lines.extend(_format_ingest_section("Ingest (required)", ingest.get("required") or []))
    lines.append("")
    lines.extend(_format_ingest_section("Ingest (optional)", ingest.get("optional") or []))
    lines.append("")

    lines.append("Context snapshots")
    snapshots = report.get("context_snapshots") or []
    if not snapshots:
        lines.append("  (none)")
    else:
        for row in snapshots:
            age = format_age(row.get("age_seconds"))
            lines.append(f"  {row['scope']:<8} {row['as_of']}  ({age})")
    lines.append("")

    portfolio = report.get("portfolio_snapshot")
    if portfolio:
        age = format_age(portfolio.get("age_seconds"))
        nav = portfolio.get("nav_usd")
        nav_part = f"  NAV ${nav}" if nav is not None else ""
        lines.append(f"Portfolio snapshot: {portfolio['ts']}  ({age}){nav_part}")
    else:
        lines.append("Portfolio snapshot: (none)")
    lines.append("")

    mcp = report.get("mcp_health")
    if mcp is None:
        lines.append("MCP /health: (probe skipped)")
    else:
        lines.append(f"MCP /health: {mcp.get('url')}")
        if not mcp.get("reachable"):
            lines.append(f"  unreachable ({mcp.get('error', 'unknown')})")
        else:
            http = mcp.get("http_status")
            lines.append(f"  HTTP {http}  service_ok={mcp.get('service_ok')}")
            if mcp.get("ingest_ok") is not None:
                lines.append(f"  ingest_ok={mcp.get('ingest_ok')}")
            if mcp.get("status_detail"):
                lines.append(f"  detail: {mcp['status_detail']}")
            if mcp.get("error") and not mcp.get("ok"):
                lines.append(f"  error: {mcp['error']}")

    summary = report.get("summary") or {}
    lines.append("")
    overall = "OK" if summary.get("ok") else "ATTENTION"
    lines.append(f"Overall: {overall}")
    if not summary.get("ingest_ok"):
        failed = report.get("required_failures") or []
        lines.append(f"  required ingest failures: {', '.join(failed)}")
    if summary.get("mcp_ok") is False:
        lines.append("  MCP health check failed")
    return "\n".join(lines)
