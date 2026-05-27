from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from alloccontext.brief.archive import brief_archive_path
from alloccontext.brief.runner import run_brief
from alloccontext.deliver.email import email_configured, send_email
from alloccontext.synthesize.brief import synthesize_brief_markdown
from alloccontext.synthesize.prompts import build_user_prompt, system_prompt


def _minimal_context(scope: str = "daily") -> dict:
    return {
        "bundle_id": f"{scope}:2026-05-21T12:00:00+00:00",
        "scope": scope,
        "as_of": "2026-05-21T12:00:00+00:00",
        "prior_as_of": None,
        "portfolio": {"available": True, "nav_usd": 10000},
        "market": {"available": True},
        "sentiment": {"available": True},
        "macro": {"available": False, "reason": "unavailable"},
        "delta": {"available": True},
    }


def test_synthesize_stub_when_disabled(config) -> None:
    from dataclasses import replace

    cfg = replace(
        config,
        synthesis=replace(config.synthesis, enabled=False),
    )
    body = synthesize_brief_markdown(_minimal_context(), cfg, scope="daily")
    assert "Daily brief (stub)" in body
    assert "portfolio" in body


def test_synthesize_uses_llm_mock(config, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_llm(prompt, synthesis, *, system=None):
        assert "ContextBundle JSON" in prompt
        assert system == system_prompt("daily")
        return "# Daily brief\n\nLLM body here.\n\n_Not financial advice._"

    body = synthesize_brief_markdown(
        _minimal_context(),
        config,
        scope="daily",
        llm_call=fake_llm,
    )
    assert "LLM body here" in body


def test_build_user_prompt_includes_notes(config) -> None:
    prompt = build_user_prompt(
        _minimal_context(),
        scope="weekly",
        portfolio_notes="Hold ETH core.",
        prompt_version="weekly_brief_v1",
    )
    assert "weekly_brief_v1" in prompt
    assert "Hold ETH core." in prompt
    assert "Monday-morning recap" in prompt


def test_email_configured_resend(monkeypatch, config) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "Analyst <onboarding@resend.dev>")
    monkeypatch.setenv("EMAIL_TO", "me@example.com")
    assert email_configured(config.deliver.email) is True


def test_email_not_configured_without_resend_key(monkeypatch, config) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("RESEND_FROM", "Analyst <onboarding@resend.dev>")
    monkeypatch.setenv("EMAIL_TO", "me@example.com")
    assert email_configured(config.deliver.email) is False


def test_send_email_resend(monkeypatch, config) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "Analyst <onboarding@resend.dev>")
    monkeypatch.setenv("EMAIL_TO", "me@example.com")

    sent: dict = {}

    def fake_resend(**kwargs):
        sent.update(kwargs)
        return {"provider": "resend", "id": "msg_123"}

    monkeypatch.setattr("alloccontext.deliver.email.send_via_resend", fake_resend)
    result = send_email(
        subject="Test",
        body="Hello",
        config=config.deliver.email,
    )
    assert result == {"provider": "resend", "id": "msg_123"}
    assert sent["subject"] == "Test"
    assert sent["to_addr"] == "me@example.com"


def test_send_email_renders_markdown(monkeypatch, config) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "Analyst <onboarding@resend.dev>")
    monkeypatch.setenv("EMAIL_TO", "me@example.com")

    sent: dict = {}

    def fake_resend(**kwargs):
        sent.update(kwargs)
        return {"provider": "resend", "id": "msg_123"}

    monkeypatch.setattr("alloccontext.deliver.email.send_via_resend", fake_resend)
    send_email(
        subject="Test",
        body="## Portfolio snapshot\n\nNAV **$10k**.",
        config=config.deliver.email,
    )
    assert sent["html"] is not None
    assert "<h2" in sent["html"]
    assert "##" not in sent["body"]
    assert "**" not in sent["body"]
    assert "Portfolio snapshot" in sent["body"]


def test_send_email_requires_resend_key(monkeypatch, config) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("RESEND_FROM", "Analyst <onboarding@resend.dev>")
    monkeypatch.setenv("EMAIL_TO", "me@example.com")

    try:
        send_email(subject="Test", body="Hello", config=config.deliver.email)
    except RuntimeError as exc:
        assert "RESEND_API_KEY" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_brief_archive_path() -> None:
    path = brief_archive_path(
        Path("/tmp/briefs"),
        scope="weekly",
        as_of_iso="2026-05-21T12:00:00+00:00",
    )
    assert path == Path("/tmp/briefs/weekly/2026-W21.md")


def test_run_brief_stdout_and_archive(config, tmp_path: Path, capsys) -> None:
    from dataclasses import replace

    as_of = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    cfg = replace(
        config,
        paths=replace(config.paths, brief_archive_dir=tmp_path / "briefs"),
        synthesis=replace(config.synthesis, enabled=False),
    )
    result = run_brief(cfg, scope="daily", stdout=True, as_of=as_of)
    out = capsys.readouterr().out
    assert "Daily brief (stub)" in out
    assert result["archive_path"].endswith("2026-05-21.md")
    assert Path(result["archive_path"]).exists()


def test_run_brief_email(config, tmp_path: Path, monkeypatch) -> None:
    from dataclasses import replace

    cfg = replace(
        config,
        paths=replace(config.paths, brief_archive_dir=tmp_path / "briefs"),
        synthesis=replace(config.synthesis, enabled=False),
    )
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "Analyst <onboarding@resend.dev>")
    monkeypatch.setenv("EMAIL_TO", "b@example.com")

    with patch("alloccontext.brief.runner.send_email") as mock_send:
        mock_send.return_value = {"provider": "resend", "id": "msg_123"}
        result = run_brief(cfg, scope="daily", email=True)

    assert result["delivered_via"] == "email"
    mock_send.assert_called_once()
    assert "Daily brief" in mock_send.call_args.kwargs["subject"]
