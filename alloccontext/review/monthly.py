from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from alloccontext.deliver.email import email_configured, send_email
from alloccontext.predictions.store import list_predictions, update_prediction_status
from alloccontext.rollup.context import build_context_bundle
from alloccontext.synthesize.openai import openai_chat

ReviewFn = Callable[..., str]


def _default_month(now: datetime | None = None) -> str:
    ts = now or datetime.now(timezone.utc)
    first_of_month = ts.replace(day=1)
    prior = first_of_month - timedelta(days=1)
    return prior.strftime("%Y-%m")


def _brief_stats(conn: sqlite3.Connection, month: str) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT scope, COUNT(*) AS n
        FROM brief_archive
        WHERE strftime('%Y-%m', as_of) = ?
        GROUP BY scope
        """,
        (month,),
    ).fetchall()
    stats = {"daily": 0, "weekly": 0}
    for row in rows:
        stats[str(row["scope"])] = int(row["n"])
    return stats


def _status_counts(predictions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in predictions:
        status = str(row.get("status") or "open")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _format_prediction_table(predictions: list[dict[str, Any]]) -> list[str]:
    lines = ["| ID | Brief | Condition | Watch | By | Status |", "|---|---|---|---|---|---|"]
    for row in predictions:
        lines.append(
            "| {id} | {scope} {as_of} | {cond} | {watch} | {by} | {status} |".format(
                id=row["id"],
                scope=row["scope"],
                as_of=str(row["brief_as_of"])[:10],
                cond=str(row["condition_text"]).replace("|", "/"),
                watch=str(row["watch_text"]).replace("|", "/"),
                by=str(row.get("by_text") or "—"),
                status=row.get("status") or "open",
            )
        )
    return lines


def _review_system_prompt() -> str:
    return (
        "You score forward watches from prior market briefs against the current "
        "ContextBundle. Use ONLY provided data. Return valid JSON array with one "
        "object per prediction id: "
        '{"id": number, "status": "hit"|"miss"|"partial"|"expired"|"open", '
        '"notes": "one sentence rationale"}. '
        "Be conservative — mark hit only when evidence clearly supports the watch."
    )


def _build_review_prompt(
    predictions: list[dict[str, Any]],
    context: dict[str, Any],
    month: str,
) -> str:
    payload = {
        "review_month": month,
        "predictions": predictions,
        "current_context_bundle": context,
    }
    return (
        "Score each prediction against current market facts.\n\n"
        f"{json.dumps(payload, indent=2, default=str)}\n"
    )


def _parse_review_scores(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("review response missing JSON array")
    return json.loads(text[start : end + 1])


def run_monthly_review(
    conn: sqlite3.Connection,
    config,
    *,
    month: str | None = None,
    stdout: bool = False,
    email: bool = False,
    apply: bool = False,
    llm_call: ReviewFn | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    review_month = month or _default_month(as_of)
    predictions = list_predictions(conn, month=review_month)
    stats = _brief_stats(conn, review_month)
    counts = _status_counts(predictions)

    context = build_context_bundle(
        conn, config, scope="weekly", rollup=config.rollup, as_of=as_of
    )
    scores: list[dict[str, Any]] = []
    review_error: str | None = None

    if predictions and config.synthesis.enabled:
        try:
            prompt = _build_review_prompt(predictions, context, review_month)
            call = llm_call or openai_chat
            raw = call(
                prompt,
                config.synthesis,
                system=_review_system_prompt(),
            )
            scores = _parse_review_scores(raw)
            if apply:
                allowed_ids = {int(row["id"]) for row in predictions}
                for item in scores:
                    pid = int(item["id"])
                    if pid not in allowed_ids:
                        continue
                    status = str(item.get("status") or "open")
                    if status not in {"hit", "miss", "partial", "expired", "open"}:
                        continue
                    if status == "open":
                        continue
                    update_prediction_status(
                        conn,
                        pid,
                        status=status,  # type: ignore[arg-type]
                        outcome_notes=str(item.get("notes") or "").strip() or None,
                    )
                conn.commit()
        except Exception as exc:  # noqa: BLE001 — surface review failure in report
            review_error = str(exc)

    lines = [
        f"# Monthly review — {review_month}",
        "",
        "## Brief activity",
        f"- Daily briefs archived: {stats['daily']}",
        f"- Weekly briefs archived: {stats['weekly']}",
        "",
        "## Forward watches",
        f"- Total logged: {len(predictions)}",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- {status}: {count}")

    if predictions:
        lines.extend(["", *_format_prediction_table(predictions)])
    else:
        lines.extend(["", "_No forward watches logged for this month._"])

    if scores:
        lines.extend(["", "## LLM scoring", ""])
        for item in scores:
            lines.append(
                f"- #{item.get('id')}: **{item.get('status')}** — "
                f"{item.get('notes', '').strip()}"
            )
    elif review_error:
        lines.extend(["", f"_LLM review unavailable: {review_error}_"])
    elif not predictions:
        lines.extend(["", "_Skipping LLM review — no predictions._"])
    else:
        lines.extend(["", "_LLM review skipped (synthesis disabled or no API key)._"])

    lines.extend(["", "_Not financial advice._"])
    body = "\n".join(lines)

    delivered_via: str | None = None
    if stdout:
        print(body)
        delivered_via = "stdout"
    if email:
        if not email_configured(config.deliver.email):
            raise RuntimeError(
                "Email not configured — set RESEND_API_KEY, RESEND_FROM, and EMAIL_TO"
            )
        send_email(
            subject=f"AllocContext — Monthly review {review_month}",
            body=body,
            config=config.deliver.email,
        )
        delivered_via = "email" if delivered_via is None else f"{delivered_via}+email"

    return {
        "ok": True,
        "month": review_month,
        "prediction_count": len(predictions),
        "brief_stats": stats,
        "status_counts": counts,
        "scores_applied": apply and bool(scores),
        "delivered_via": delivered_via,
        "body_chars": len(body),
    }
