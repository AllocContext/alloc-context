from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

Scope = Literal["daily", "weekly"]


def _sum_flows(rows) -> float | None:
    values = [float(row["net_flow_usd"]) for row in rows if row["net_flow_usd"] is not None]
    if not values:
        return None
    return round(sum(values), 2)


def _latest_flow_row(conn, asset: str):
    return conn.execute(
        """
        SELECT flow_date, net_flow_usd, total_net_assets_usd, cum_net_inflow_usd, source
        FROM etf_flow_days
        WHERE asset = ?
        ORDER BY flow_date DESC
        LIMIT 1
        """,
        (asset,),
    ).fetchone()


def _flows_since(conn, asset: str, since_date: str) -> list:
    return conn.execute(
        """
        SELECT flow_date, net_flow_usd
        FROM etf_flow_days
        WHERE asset = ? AND flow_date >= ?
        ORDER BY flow_date ASC
        """,
        (asset, since_date),
    ).fetchall()


def _ticker_breakdown(conn, asset: str, flow_date: str | None) -> dict[str, float]:
    if not flow_date:
        return {}
    rows = conn.execute(
        """
        SELECT ticker, net_flow_usd
        FROM etf_ticker_flows
        WHERE asset = ? AND flow_date = ?
        ORDER BY ABS(COALESCE(net_flow_usd, 0)) DESC
        """,
        (asset, flow_date),
    ).fetchall()
    out: dict[str, float] = {}
    for row in rows:
        if row["net_flow_usd"] is None:
            continue
        out[str(row["ticker"])] = round(float(row["net_flow_usd"]), 2)
    return out


def build_etf_asset_context(conn, *, asset: str, now: datetime, scope: Scope) -> dict[str, Any]:
    latest = _latest_flow_row(conn, asset)
    if latest is None:
        return {"available": False, "reason": "no_data"}

    window_days = 1 if scope == "daily" else 7
    since = (now.date() - timedelta(days=window_days - 1)).isoformat()
    window_rows = _flows_since(conn, asset, since)
    net_window = _sum_flows(window_rows)

    result: dict[str, Any] = {
        "available": True,
        "as_of_date": latest["flow_date"],
        "source": latest["source"],
        "net_flow_usd_1d": (
            round(float(latest["net_flow_usd"]), 2)
            if latest["net_flow_usd"] is not None
            else None
        ),
        "net_flow_usd_7d": net_window if scope == "weekly" else _sum_flows(_flows_since(
            conn,
            asset,
            (now.date() - timedelta(days=6)).isoformat(),
        )),
        "total_net_assets_usd": (
            round(float(latest["total_net_assets_usd"]), 2)
            if latest["total_net_assets_usd"] is not None
            else None
        ),
        "by_ticker": _ticker_breakdown(conn, asset, latest["flow_date"]),
    }
    if scope == "daily":
        result["net_flow_usd_24h"] = result["net_flow_usd_1d"]
    return result


def build_etf_context(conn, *, now: datetime, scope: Scope, assets: list[str]) -> dict[str, Any]:
    blocks: dict[str, Any] = {}
    sources: set[str] = set()
    for asset in assets:
        block = build_etf_asset_context(conn, asset=asset, now=now, scope=scope)
        blocks[asset.lower()] = block
        if block.get("available") and block.get("source"):
            sources.add(str(block["source"]))

    if not any(block.get("available") for block in blocks.values()):
        return {"available": False, "reason": "no_etf_data"}

    return {
        "available": True,
        "assets": blocks,
        "sources": sorted(sources),
    }
