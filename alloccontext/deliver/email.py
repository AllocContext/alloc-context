from __future__ import annotations

import os
from typing import Any

from alloccontext.config import EmailConfig
from alloccontext.deliver.render import render_markdown_email
from alloccontext.deliver.resend import resend_api_key, send_via_resend


def _env_address(config: EmailConfig, *, kind: str) -> str | None:
    if kind == "from":
        return os.environ.get("EMAIL_FROM") or config.from_address
    return os.environ.get("EMAIL_TO") or config.to_address


def _from_address(config: EmailConfig) -> str | None:
    return os.environ.get("RESEND_FROM") or _env_address(config, kind="from")


def email_configured(config: EmailConfig) -> bool:
    if not config.enabled:
        return False
    if not resend_api_key():
        return False
    return bool(_from_address(config) and _env_address(config, kind="to"))


def send_email(
    *,
    subject: str,
    body: str,
    config: EmailConfig,
    markdown: bool = True,
) -> dict[str, Any]:
    if not config.enabled:
        raise RuntimeError("Email delivery disabled in config")

    to_addr = _env_address(config, kind="to")
    from_addr = _from_address(config)
    if not resend_api_key():
        raise RuntimeError("Email not configured — set RESEND_API_KEY")
    if not to_addr or not from_addr:
        raise RuntimeError(
            "EMAIL_TO and RESEND_FROM (or EMAIL_FROM) required for email delivery"
        )

    text_body = body
    html_body: str | None = None
    if markdown:
        text_body, html_body = render_markdown_email(body)

    return send_via_resend(
        subject=subject,
        body=text_body,
        html=html_body,
        from_addr=from_addr,
        to_addr=to_addr,
    )
