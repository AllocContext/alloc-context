from __future__ import annotations

from pathlib import Path

import pytest

from alloccontext.user_config import (
    DEFAULT_UPSTREAM_URL,
    UserConfig,
    load_user_config,
    resolve_user_config_path,
)


def test_load_user_config_empty_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"
    user = load_user_config(path)
    assert user.path == path
    assert user.upstream == DEFAULT_UPSTREAM_URL
    assert user.self_host is False
    assert user.primary_exchange_credentials() is None


def test_load_user_config_full(tmp_path: Path) -> None:
    path = tmp_path / "user.yaml"
    path.write_text(
        """
upstream: https://example.com/mcp
self_host: false
exchanges:
  primary: kraken
  kraken:
    api_key: key
    api_secret: secret
target_allocation:
  BTC: 0.7
  ETH: 0.3
  CASH: 0.0
band: 0.15
x402:
  payer_private_key_env: TEST_PAYER_KEY
  payer_private_key_file: /tmp/payer.key
""",
        encoding="utf-8",
    )
    user = load_user_config(path)
    assert user.upstream == "https://example.com/mcp"
    creds = user.primary_exchange_credentials()
    assert creds is not None
    assert creds.exchange_id == "kraken"
    assert creds.api_key == "key"
    assert user.target_allocation == {"BTC": 0.7, "ETH": 0.3, "CASH": 0.0}
    assert user.band == 0.15
    assert user.x402.payer_private_key_env == "TEST_PAYER_KEY"
    assert user.x402.payer_private_key_file == "/tmp/payer.key"


def test_resolve_user_config_path_explicit(tmp_path: Path) -> None:
    path = tmp_path / "user.yaml"
    path.touch()
    assert resolve_user_config_path(str(path)) == path.resolve()


def test_user_config_empty_factory() -> None:
    user = UserConfig.empty()
    assert user.uses_upstream() is True
