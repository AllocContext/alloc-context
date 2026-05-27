from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_brief_timers_do_not_use_persistent_catchup() -> None:
    for name in (
        "alloc-context-daily-brief.timer",
        "alloc-context-weekly-brief.timer",
    ):
        text = (REPO_ROOT / "deploy/systemd" / name).read_text()
        assert "Persistent=true" not in text


def test_ingest_timer_runs_hourly() -> None:
    text = (REPO_ROOT / "deploy/systemd/alloc-context-ingest.timer").read_text()
    assert "OnCalendar=hourly" in text


def test_ingest_timer_keeps_persistent_catchup() -> None:
    text = (REPO_ROOT / "deploy/systemd/alloc-context-ingest.timer").read_text()
    assert "Persistent=true" in text


def test_remote_install_avoids_restarting_active_timers() -> None:
    text = (REPO_ROOT / "deploy/remote-install.sh").read_text()
    assert "_enable_timer" in text
    assert "is-active --quiet" in text
