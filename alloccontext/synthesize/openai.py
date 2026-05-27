from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable

from alloccontext.config import SynthesisConfig

ChatFn = Callable[[str, SynthesisConfig, str | None], str]


def openai_chat(
    prompt: str,
    synthesis: SynthesisConfig,
    *,
    system: str | None = None,
) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    body = {
        "model": synthesis.model,
        "temperature": synthesis.temperature,
        "messages": [
            {
                "role": "system",
                "content": system
                or (
                    "You are a personal crypto market analyst. Use ONLY the "
                    "data provided. Never invent numbers. End with a brief "
                    "not-financial-advice line."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=synthesis.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail}") from exc

    content = payload["choices"][0]["message"]["content"]
    return str(content).strip()
