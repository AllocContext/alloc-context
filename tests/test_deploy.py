from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


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


def test_core_deploy_installs_ingest_and_mcp_http() -> None:
    text = (REPO_ROOT / "deploy/remote-install.sh").read_text()
    install_block = text.split("for unit in")[1].split("done")[0]
    assert "alloc-context-ingest.service" in install_block
    assert "alloc-context-mcp-http.service" in install_block
    assert "alloc-context-backup.timer" in install_block
    assert "daily-brief" not in install_block
    assert "alerts.timer" not in install_block


def test_remote_install_restarts_mcp_services() -> None:
    text = (REPO_ROOT / "deploy/remote-install.sh").read_text()
    assert "systemctl restart alloc-context-mcp-http.service" in text
    assert "alloc-context-mcp-internal.service" in text
    assert "wait-for-mcp-ready.sh" in text


def test_wait_for_mcp_ready_script_exists() -> None:
    path = REPO_ROOT / "deploy/wait-for-mcp-ready.sh"
    assert path.is_file()
    text = path.read_text()
    assert "8000/health" in text
    assert "8001/mcp" in text


def test_mcp_http_systemd_unit() -> None:
    text = (REPO_ROOT / "deploy/systemd/alloc-context-mcp-http.service").read_text()
    assert "--port 8000" in text
    assert "--x402" in text


def test_mcp_internal_systemd_unit() -> None:
    text = (REPO_ROOT / "deploy/systemd/alloc-context-mcp-internal.service").read_text()
    assert "--port 8001" in text
    assert "--x402" not in text


def test_remote_install_substitutes_environment_file() -> None:
    text = (REPO_ROOT / "deploy/remote-install.sh").read_text()
    assert "EnvironmentFile=/.*" in text
    assert "EnvironmentFile=-${ENV_FILE}" in text
