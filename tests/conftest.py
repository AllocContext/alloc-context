from __future__ import annotations

from pathlib import Path

import pytest

from alloccontext.config import load_config
from alloccontext.store.db import connect


@pytest.fixture
def config(tmp_path: Path):
    db = tmp_path / "test.db"
    cfg_path = tmp_path / "config.yaml"
    example = Path("config/config.example.yaml").read_text()
    cfg_path.write_text(example.replace("state/alloccontext.db", str(db)))
    return load_config(cfg_path)


@pytest.fixture
def conn(config):
    connection = connect(config.paths.db)
    yield connection
    connection.close()


@pytest.fixture
def mock_live_ingest_ok(monkeypatch):
    """Stub successful full ingest for freshness=live MCP handler tests."""

    def _ok_ingest(_conn, _config):
        return {
            "ok": True,
            "errors": {},
            "counts": {},
            "fatal_errors": {},
        }

    monkeypatch.setattr("alloccontext.ingest.runner.run_ingest", _ok_ingest)
