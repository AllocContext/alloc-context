from __future__ import annotations

from pathlib import Path

import pytest

from alloccontext.mcp.payer import PayerKeyError, resolve_payer_private_key_from_config
from alloccontext.user_config import X402PayerConfig


def test_resolve_payer_file_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key_file = tmp_path / "payer.key"
    key_file.write_text("0xabc123\n", encoding="utf-8")
    monkeypatch.delenv("EVM_PRIVATE_KEY", raising=False)
    x402 = X402PayerConfig(
        payer_private_key_file=str(key_file),
        payer_private_key="0xdead",
        payer_private_key_env="EVM_PRIVATE_KEY",
    )
    assert resolve_payer_private_key_from_config(x402) == "0xabc123"


def test_resolve_payer_inline_second(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVM_PRIVATE_KEY", raising=False)
    x402 = X402PayerConfig(payer_private_key="0xdead")
    assert resolve_payer_private_key_from_config(x402) == "0xdead"


def test_resolve_payer_env_third(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVM_PRIVATE_KEY", "0xfeed")
    x402 = X402PayerConfig()
    assert resolve_payer_private_key_from_config(x402) == "0xfeed"


def test_resolve_payer_missing_file(tmp_path: Path) -> None:
    x402 = X402PayerConfig(payer_private_key_file=str(tmp_path / "missing.key"))
    with pytest.raises(PayerKeyError, match="not found"):
        resolve_payer_private_key_from_config(x402)
