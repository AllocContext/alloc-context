from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_USER_CONFIG_PATH = Path.home() / ".config" / "alloc-context" / "user.yaml"
DEFAULT_UPSTREAM_URL = "https://mcp.alloc-context.com/mcp"
DEFAULT_PAYER_ENV = "EVM_PRIVATE_KEY"
ENV_USER_CONFIG = "ALLOC_CONTEXT_USER_CONFIG"


@dataclass(frozen=True)
class ExchangeCredentials:
    exchange_id: str
    api_key: str
    api_secret: str


@dataclass(frozen=True)
class X402PayerConfig:
    payer_private_key_env: str = DEFAULT_PAYER_ENV
    payer_private_key_file: str | None = None
    payer_private_key: str | None = None


@dataclass(frozen=True)
class UserConfig:
    path: Path | None
    upstream: str
    self_host: bool
    server_config: str | None
    primary_exchange: str | None
    exchanges: dict[str, ExchangeCredentials]
    target_allocation: dict[str, float] | None
    band: float | None
    theses: list[dict[str, Any]] | None
    x402: X402PayerConfig

    @classmethod
    def empty(cls, *, path: Path | None = None) -> UserConfig:
        return cls(
            path=path,
            upstream=DEFAULT_UPSTREAM_URL,
            self_host=False,
            server_config=None,
            primary_exchange=None,
            exchanges={},
            target_allocation=None,
            band=None,
            theses=None,
            x402=X402PayerConfig(),
        )

    def primary_exchange_credentials(self) -> ExchangeCredentials | None:
        if not self.primary_exchange:
            return None
        return self.exchanges.get(self.primary_exchange)

    def uses_upstream(self) -> bool:
        return not self.self_host


def resolve_user_config_path(explicit: str | None = None) -> Path | None:
    if explicit:
        return _expand_path(explicit)
    env_path = os.environ.get(ENV_USER_CONFIG, "").strip()
    if env_path:
        return _expand_path(env_path)
    default = DEFAULT_USER_CONFIG_PATH
    if default.is_file():
        return default
    return None


def _expand_path(raw: str) -> Path:
    return Path(os.path.expanduser(raw.strip())).resolve()


def _normalize_exchange_id(raw: str) -> str:
    key = raw.strip().lower()
    if key not in ("kraken", "coinbase"):
        raise ValueError(f"unsupported exchange {raw!r}; use kraken or coinbase")
    return key


def _parse_exchange_block(block: dict[str, Any]) -> ExchangeCredentials:
    api_key = str(block.get("api_key") or "").strip()
    api_secret = str(block.get("api_secret") or "").strip()
    if not api_key or not api_secret:
        raise ValueError("exchange requires api_key and api_secret")
    return ExchangeCredentials(
        exchange_id="",
        api_key=api_key,
        api_secret=api_secret,
    )


def _parse_theses(raw: Any) -> list[dict[str, Any]] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("theses must be a list")
    result: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each thesis entry must be a mapping")
        result.append(dict(entry))
    return result or None


def _parse_target_allocation(raw: Any) -> dict[str, float] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("target_allocation must be a mapping")
    result: dict[str, float] = {}
    for key, value in raw.items():
        asset = str(key).strip().upper()
        if not asset:
            continue
        result[asset] = float(value)
    return result or None


def load_user_config(path: Path | None) -> UserConfig:
    if path is None:
        return UserConfig.empty()
    if not path.is_file():
        return UserConfig.empty(path=path)

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"user config must be a YAML mapping: {path}")

    upstream = str(data.get("upstream") or DEFAULT_UPSTREAM_URL).strip()
    self_host = bool(data.get("self_host"))
    server_config = data.get("config")
    server_config_path = str(server_config).strip() if server_config else None

    exchanges_raw = data.get("exchanges") or {}
    if not isinstance(exchanges_raw, dict):
        raise ValueError("exchanges must be a mapping")
    primary = exchanges_raw.get("primary")
    primary_exchange = _normalize_exchange_id(str(primary)) if primary else None

    exchanges: dict[str, ExchangeCredentials] = {}
    for key, value in exchanges_raw.items():
        if key == "primary" or not isinstance(value, dict):
            continue
        exchange_id = _normalize_exchange_id(str(key))
        creds = _parse_exchange_block(value)
        exchanges[exchange_id] = ExchangeCredentials(
            exchange_id=exchange_id,
            api_key=creds.api_key,
            api_secret=creds.api_secret,
        )

    x402_raw = data.get("x402") or {}
    if x402_raw and not isinstance(x402_raw, dict):
        raise ValueError("x402 must be a mapping")
    payer_file = x402_raw.get("payer_private_key_file")
    payer_file_path = str(payer_file).strip() if payer_file else None
    payer_inline = x402_raw.get("payer_private_key")
    payer_inline_key = str(payer_inline).strip() if payer_inline else None
    payer_env = str(x402_raw.get("payer_private_key_env") or DEFAULT_PAYER_ENV).strip()

    band_raw = data.get("band")
    band = float(band_raw) if band_raw is not None else None

    theses = _parse_theses(data.get("theses"))
    if theses:
        from alloccontext.mcp.validation import McpValidationError, validate_theses

        try:
            validate_theses(theses)
        except McpValidationError as exc:
            raise ValueError(str(exc)) from exc

    return UserConfig(
        path=path,
        upstream=upstream,
        self_host=self_host,
        server_config=server_config_path,
        primary_exchange=primary_exchange,
        exchanges=exchanges,
        target_allocation=_parse_target_allocation(data.get("target_allocation")),
        band=band,
        theses=theses,
        x402=X402PayerConfig(
            payer_private_key_env=payer_env or DEFAULT_PAYER_ENV,
            payer_private_key_file=payer_file_path,
            payer_private_key=payer_inline_key,
        ),
    )
