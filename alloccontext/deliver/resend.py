from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def resend_api_key() -> str | None:
    return os.environ.get("RESEND_API_KEY") or None


def send_via_resend(
    *,
    subject: str,
    body: str,
    from_addr: str,
    to_addr: str,
    api_key: str | None = None,
    html: str | None = None,
) -> dict[str, Any]:
    key = api_key or resend_api_key()
    if not key:
        raise RuntimeError("RESEND_API_KEY not set")

    payload: dict[str, Any] = {
        "from": from_addr,
        "to": [to_addr],
        "subject": subject,
        "text": body,
    }
    if html:
        payload["html"] = html
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "alloc-context/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Resend API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Resend API unreachable: {exc.reason}") from exc

    return {"provider": "resend", "id": raw.get("id")}
