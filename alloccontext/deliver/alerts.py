from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from alloccontext.deliver.email import email_configured, send_email
from alloccontext.rollup.context import build_context_bundle
from alloccontext.rollup.portfolio import build_portfolio_context
from alloccontext.synthesize.allocation_advice import asset_label, synthesize_allocation_advice


from alloccontext.timeutil import utc_now


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def evaluate_rebalance_alert(portfolio: dict[str, Any], config) -> dict[str, Any] | None:
    if not portfolio.get("available"):
        return None
    hint = str(portfolio.get("rebalance_hint") or "within_band")
    if hint == "within_band":
        return None
    if not config.deliver.alerts.triggers.rebalance_band:
        return None
    return {
        "trigger_key": "rebalance_band",
        "dedupe_key": f"rebalance_band:{hint}",
        "hint": hint,
        "portfolio": portfolio,
    }


def _recent_alerts(conn: sqlite3.Connection, *, since: datetime) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT trigger_key, dedupe_key, fired_at, delivered_via
        FROM alert_log
        WHERE fired_at >= ? AND delivered_via IS NOT NULL
        ORDER BY fired_at DESC
        """,
        (since.isoformat(),),
    ).fetchall()


def _delivery_allowed(
    conn: sqlite3.Connection,
    config,
    candidate: dict[str, Any],
    *,
    now: datetime,
) -> tuple[bool, str | None]:
    alerts = config.deliver.alerts
    since_7d = now - timedelta(days=7)
    since_cooldown = now - timedelta(hours=alerts.min_hours_between)
    since_dedupe = now - timedelta(hours=alerts.dedupe_hours)

    recent = _recent_alerts(conn, since=since_7d)
    if len(recent) >= alerts.max_per_7d:
        return False, "max_per_7d"

    for row in recent:
        fired = _parse_iso(str(row["fired_at"]))
        if fired >= since_cooldown:
            return False, "min_hours_between"
        if (
            str(row["dedupe_key"]) == candidate["dedupe_key"]
            and fired >= since_dedupe
        ):
            return False, "dedupe"

    return True, None


def _format_alert_body(
    candidate: dict[str, Any],
    config,
    *,
    allocation_advice: str | None = None,
) -> str:
    portfolio = candidate["portfolio"]
    allocation = portfolio.get("allocation_pct") or {}
    target = portfolio.get("target_allocation_pct") or {}
    drift = portfolio.get("drift") or {}
    band = config.portfolio.rebalance_band

    lines = [
        "**Allocation band alert**",
        "",
        f"Trigger: `{candidate['trigger_key']}`",
        f"Hint: `{candidate['hint']}`",
        "",
        f"NAV: ${portfolio.get('nav_usd', 0):,.2f}",
        f"Cash: ${portfolio.get('cash_usd', 0):,.2f}",
        "",
        "Current vs target (pct points drift):",
    ]
    for asset in ("BTC", "ETH", "CASH"):
        cur = allocation.get(asset)
        tgt = target.get(asset)
        d = drift.get(asset)
        if cur is None:
            continue
        lines.append(
            f"- {asset_label(asset)}: {float(cur) * 100:.1f}% "
            f"(target {float(tgt or 0) * 100:.1f}%, drift {float(d or 0) * 100:+.1f})"
        )
    lines.extend(
        [
            "",
            f"Rebalance band: ±{band * 100:.0f}%",
        ]
    )
    if allocation_advice:
        lines.extend(
            [
                "",
                "**Suggested allocation**",
                "",
                allocation_advice.strip(),
            ]
        )
    lines.extend(
        [
            "",
            "Open Kraken to review allocation — no automated trades.",
            "",
            "_Not financial advice._",
        ]
    )
    return "\n".join(lines)


def record_alert(
    conn: sqlite3.Connection,
    candidate: dict[str, Any],
    *,
    delivered_via: str | None,
    fired_at: datetime,
) -> None:
    conn.execute(
        """
        INSERT INTO alert_log(trigger_key, dedupe_key, fired_at, delivered_via, context_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            candidate["trigger_key"],
            candidate["dedupe_key"],
            fired_at.isoformat(),
            delivered_via,
            json.dumps({"portfolio": candidate.get("portfolio")}),
        ),
    )
    conn.commit()


def check_alerts(
    conn: sqlite3.Connection,
    config,
    *,
    email: bool = True,
    stdout: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate alert triggers after ingest; email when policy allows."""
    if not config.deliver.alerts.enabled:
        return {"ok": True, "skipped": True, "reason": "alerts_disabled"}

    ts = now or utc_now()
    portfolio = build_portfolio_context(conn, config)
    candidate = evaluate_rebalance_alert(portfolio, config)
    if candidate is None:
        return {"ok": True, "fired": False, "reason": "no_trigger"}

    allowed, block_reason = _delivery_allowed(conn, config, candidate, now=ts)
    context = build_context_bundle(
        conn,
        config,
        scope="daily",
        rollup=config.rollup,
        as_of=ts,
    )
    allocation_advice = synthesize_allocation_advice(
        context,
        config,
        hint=str(candidate["hint"]),
    )
    body = _format_alert_body(
        candidate,
        config,
        allocation_advice=allocation_advice,
    )
    delivered_via: str | None = None

    if allowed:
        if stdout:
            print(body)
            delivered_via = "stdout"
        if email and email_configured(config.deliver.email):
            send_email(
                subject="AllocContext — Allocation band alert",
                body=body,
                config=config.deliver.email,
            )
            delivered_via = "email" if delivered_via is None else f"{delivered_via}+email"
        if delivered_via is None:
            record_alert(conn, candidate, delivered_via=None, fired_at=ts)
            return {
                "ok": True,
                "fired": False,
                "suppressed": True,
                "reason": "no_delivery_channel",
                "trigger_key": candidate["trigger_key"],
                "hint": candidate["hint"],
            }
        record_alert(conn, candidate, delivered_via=delivered_via, fired_at=ts)
        return {
            "ok": True,
            "fired": True,
            "delivered_via": delivered_via,
            "trigger_key": candidate["trigger_key"],
            "hint": candidate["hint"],
        }

    record_alert(conn, candidate, delivered_via=None, fired_at=ts)
    return {
        "ok": True,
        "fired": False,
        "suppressed": True,
        "reason": block_reason,
        "trigger_key": candidate["trigger_key"],
        "hint": candidate["hint"],
    }
