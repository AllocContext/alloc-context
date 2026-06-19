from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any

from alloccontext.config import RegimeCycleConfig


def _spread_pct(profit_pct: float, loss_pct: float) -> float:
    return abs(profit_pct - loss_pct)


def _row_metrics(row: sqlite3.Row) -> dict[str, float]:
    profit = float(row["supply_profit_pct"])
    loss = float(row["supply_loss_pct"])
    return {
        "supply_profit_pct": profit,
        "supply_loss_pct": loss,
        "spread_pct": _spread_pct(profit, loss),
    }


def _history_row(
    conn: sqlite3.Connection,
    *,
    as_of_date: str,
    min_age_days: int,
    max_age_days: int,
) -> sqlite3.Row | None:
    current = date.fromisoformat(as_of_date)
    oldest = (current - timedelta(days=max_age_days)).isoformat()
    newest = (current - timedelta(days=min_age_days)).isoformat()
    return conn.execute(
        """
        SELECT as_of_date, supply_profit_pct, supply_loss_pct
        FROM onchain_cycle_daily
        WHERE as_of_date <= ? AND as_of_date >= ?
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        (newest, oldest),
    ).fetchone()


def _build_history_7d(
    conn: sqlite3.Connection,
    *,
    latest: sqlite3.Row,
    thresholds: RegimeCycleConfig,
) -> dict[str, Any]:
    prior = _history_row(
        conn,
        as_of_date=str(latest["as_of_date"]),
        min_age_days=thresholds.history_7d_min_days,
        max_age_days=thresholds.history_7d_max_days,
    )
    if prior is None:
        return {"available": False}
    current = _row_metrics(latest)
    previous = _row_metrics(prior)
    return {
        "available": True,
        "spread_pct_delta": round(current["spread_pct"] - previous["spread_pct"], 2),
        "supply_profit_pct_delta": round(
            current["supply_profit_pct"] - previous["supply_profit_pct"],
            2,
        ),
        "supply_loss_pct_delta": round(
            current["supply_loss_pct"] - previous["supply_loss_pct"],
            2,
        ),
    }


def _evaluate_phase(
    *,
    metrics: dict[str, float],
    history: dict[str, Any],
    thresholds: RegimeCycleConfig,
) -> tuple[str, str]:
    spread = metrics["spread_pct"]
    profit = metrics["supply_profit_pct"]
    loss = metrics["supply_loss_pct"]
    convergence = spread <= thresholds.convergence_spread_pct

    if convergence and loss >= thresholds.capitulation_loss_floor_pct:
        return "CAPITULATION", "convergence_with_elevated_loss_supply"

    if profit >= thresholds.euphoria_profit_pct:
        return "EUPHORIA", "profit_supply_near_saturation"

    if history.get("available"):
        profit_delta = history.get("supply_profit_pct_delta")
        spread_delta = history.get("spread_pct_delta")
        if (
            profit >= thresholds.distribution_profit_pct
            and profit_delta is not None
            and profit_delta <= -thresholds.distribution_profit_drop_pct
        ):
            return "DISTRIBUTION", "profit_supply_high_and_falling"

        if (
            loss >= thresholds.recovery_loss_pct
            and spread_delta is not None
            and spread_delta >= thresholds.recovery_spread_widen_pct
        ):
            return "RECOVERY", "loss_supply_elevated_spread_widening"

    if convergence:
        return "NEUTRAL", "convergence_below_capitulation_loss_floor"
    return "NEUTRAL", "spread_above_capitulation_band"


def _unavailable(*, reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def build_cycle_context(
    conn: sqlite3.Connection,
    config,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    cycle_cfg = config.onchain.cycle
    thresholds = config.regime.cycle
    ref = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    ref_date = ref.date().isoformat()
    latest = conn.execute(
        """
        SELECT
          as_of_date,
          supply_profit_pct,
          supply_loss_pct,
          supply_profit_btc,
          supply_loss_btc,
          source,
          ingested_at
        FROM onchain_cycle_daily
        WHERE as_of_date <= ?
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        (ref_date,),
    ).fetchone()
    if latest is None:
        return _unavailable(reason="insufficient_history")

    as_of_date = str(latest["as_of_date"])
    latest_day = date.fromisoformat(as_of_date)
    staleness = (ref.date() - latest_day).days
    if staleness > cycle_cfg.max_staleness_days:
        return _unavailable(reason="stale_data")

    metrics = _row_metrics(latest)
    history = _build_history_7d(conn, latest=latest, thresholds=thresholds)
    phase, phase_reason = _evaluate_phase(
        metrics=metrics,
        history=history,
        thresholds=thresholds,
    )

    payload: dict[str, Any] = {
        "available": True,
        "as_of": as_of_date,
        "supply_profit_pct": round(metrics["supply_profit_pct"], 2),
        "supply_loss_pct": round(metrics["supply_loss_pct"], 2),
        "spread_pct": round(metrics["spread_pct"], 2),
        "convergence": metrics["spread_pct"] <= thresholds.convergence_spread_pct,
        "phase": phase,
        "phase_reason": phase_reason,
        "source": str(latest["source"]),
        "history_7d": history,
    }
    if latest["supply_profit_btc"] is not None:
        payload["supply_profit_btc"] = float(latest["supply_profit_btc"])
    if latest["supply_loss_btc"] is not None:
        payload["supply_loss_btc"] = float(latest["supply_loss_btc"])
    return payload
