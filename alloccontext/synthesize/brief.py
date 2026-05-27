from __future__ import annotations

import logging
import os
from typing import Any, Callable

from alloccontext.synthesize.openai import ChatFn, openai_chat
from alloccontext.synthesize.prompts import build_user_prompt, system_prompt

logger = logging.getLogger(__name__)


def synthesize_brief_markdown(
    context: dict[str, Any],
    config,
    *,
    scope: str,
    llm_call: ChatFn | None = None,
) -> str:
    """LLM narrative from ContextBundle, or stub when synthesis is off."""
    if not config.synthesis.enabled:
        return _stub_markdown(context, scope)

    if not os.environ.get("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not set; using stub brief")
        return _stub_markdown(context, scope)

    prompt_version = (
        config.synthesis.daily_prompt_version
        if scope == "daily"
        else config.synthesis.weekly_prompt_version
    )
    prompt = build_user_prompt(
        context,
        scope=scope,  # type: ignore[arg-type]
        portfolio_notes=config.portfolio.notes,
        prompt_version=prompt_version,
    )
    call: ChatFn = llm_call or openai_chat
    try:
        return call(
            prompt,
            config.synthesis,
            system=system_prompt(scope),  # type: ignore[arg-type]
        )
    except RuntimeError as exc:
        logger.warning("LLM synthesis failed: %s", exc)
        return _stub_markdown(context, scope, error=str(exc))


def _stub_markdown(
    context: dict[str, Any],
    scope: str,
    *,
    error: str | None = None,
) -> str:
    lines = [
        f"# {scope.title()} brief (stub)",
        "",
    ]
    if error:
        lines.extend([f"_LLM unavailable: {error}_", ""])
    lines.extend(
        [
            f"Bundle: `{context.get('bundle_id')}`",
            "",
            "Context sections:",
        ]
    )
    for section in ("portfolio", "market", "sentiment", "macro", "delta"):
        block = context.get(section) or {}
        if block.get("available") is False or "reason" in block:
            status = block.get("reason", "unavailable")
        else:
            status = "ok"
        lines.append(f"- **{section}**: {status}")
    lines.extend(["", "_Not financial advice._"])
    return "\n".join(lines)
