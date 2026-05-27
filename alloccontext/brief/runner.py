from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from alloccontext.brief.archive import write_brief_archive
from alloccontext.deliver.email import email_configured, send_email
from alloccontext.predictions.extract import extract_forward_watches
from alloccontext.predictions.store import save_predictions
from alloccontext.rollup.context import build_context_bundle
from alloccontext.store.db import connect
from alloccontext.synthesize.brief import synthesize_brief_markdown

Scope = Literal["daily", "weekly"]


def _email_subject(scope: Scope, as_of_iso: str) -> str:
    dt = datetime.fromisoformat(as_of_iso)
    if scope == "daily":
        return f"AllocContext — Daily brief {dt.date()}"
    iso = dt.date().isocalendar()
    return f"AllocContext — Weekly brief {iso.year}-W{iso.week:02d}"


def run_brief(
    config,
    *,
    scope: Scope,
    stdout: bool = False,
    email: bool = False,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    conn = connect(config.paths.db)
    context = build_context_bundle(
        conn, config, scope=scope, rollup=config.rollup, as_of=as_of
    )
    body = synthesize_brief_markdown(context, config, scope=scope)

    archive_path = write_brief_archive(
        config.paths.brief_archive_dir,
        scope=scope,
        as_of_iso=context["as_of"],
        bundle_id=str(context["bundle_id"]),
        body=body,
    )

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
            subject=_email_subject(scope, context["as_of"]),
            body=body,
            config=config.deliver.email,
        )
        delivered_via = "email" if delivered_via is None else f"{delivered_via}+email"

    as_of_iso = context["as_of"]
    conn.execute(
        """
        INSERT INTO brief_archive(scope, as_of, context_json, body_markdown, delivered_via)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(scope, as_of) DO UPDATE SET
          context_json = excluded.context_json,
          body_markdown = excluded.body_markdown,
          delivered_via = excluded.delivered_via
        """,
        (scope, as_of_iso, json.dumps(context), body, delivered_via),
    )
    watches = extract_forward_watches(body)
    prediction_count = save_predictions(
        conn,
        scope=scope,
        brief_as_of=as_of_iso,
        watches=watches,
    )
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "scope": scope,
        "as_of": as_of_iso,
        "delivered_via": delivered_via,
        "body_chars": len(body),
        "archive_path": str(archive_path),
        "prediction_count": prediction_count,
    }
