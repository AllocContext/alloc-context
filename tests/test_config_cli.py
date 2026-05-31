from __future__ import annotations

from pathlib import Path

from alloccontext.config import _resolve_config_path, load_config


def test_load_example_config() -> None:
    config = load_config("config/config.example.yaml")
    assert config.paths.db.name == "alloccontext.db"
    assert config.horizon.days == 90
    assert config.portfolio.target_allocations["BTC"] == 0.70
    assert config.ingest.sources["fear_greed"] is True


def test_resolve_config_prefers_local_yaml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ALLOC_CONTEXT_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("paths:\n  db: custom.db\n")
    (tmp_path / "config" / "config.example.yaml").write_text(
        "paths:\n  db: example.db\n"
    )
    assert _resolve_config_path(None) == Path("config/config.yaml")
    cfg = load_config()
    assert cfg.paths.db == Path("custom.db")


def test_cli_rollup_stdout(capsys) -> None:
    from alloccontext.__main__ import main

    code = main(
        ["--config", "config/config.example.yaml", "rollup", "--scope", "daily", "--stdout"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "bundle_id" in out
