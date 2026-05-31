from __future__ import annotations

import os
from pathlib import Path

from alloccontext.user_config import UserConfig, X402PayerConfig


class PayerKeyError(ValueError):
    pass


def resolve_payer_private_key(user: UserConfig) -> str | None:
    return resolve_payer_private_key_from_config(user.x402)


def resolve_payer_private_key_from_config(x402: X402PayerConfig) -> str | None:
    if x402.payer_private_key_file:
        path = Path(os.path.expanduser(x402.payer_private_key_file.strip()))
        if not path.is_file():
            raise PayerKeyError(f"x402 payer key file not found: {path}")
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            raise PayerKeyError(f"x402 payer key file is empty: {path}")
        return _normalize_hex_key(raw)

    if x402.payer_private_key:
        return _normalize_hex_key(x402.payer_private_key)

    env_name = (x402.payer_private_key_env or "").strip()
    if env_name:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return _normalize_hex_key(raw)
    return None


def _normalize_hex_key(raw: str) -> str:
    key = raw.strip()
    if key.startswith("0x"):
        key = key[2:]
    if not key:
        raise PayerKeyError("x402 payer private key is empty")
    return f"0x{key}"
