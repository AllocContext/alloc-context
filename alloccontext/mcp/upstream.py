from __future__ import annotations

import json
from typing import Any

from alloccontext.mcp.payer import PayerKeyError, resolve_payer_private_key
from alloccontext.mcp.setup import upstream_payment_required
from alloccontext.user_config import UserConfig


class UpstreamMcpError(RuntimeError):
    pass


class UpstreamPaymentRequired(Exception):
    """Raised when hosted upstream cannot be called without a payer key."""


def _unwrap_tool_result(body: dict[str, Any]) -> dict[str, Any]:
    if body.get("error"):
        raise UpstreamMcpError(str(body["error"]))
    result = body.get("result") or {}
    content = result.get("content") or []
    for block in content:
        if block.get("type") == "text":
            text = block.get("text") or ""
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise UpstreamMcpError("upstream MCP tool returned invalid JSON") from exc
    if isinstance(result, dict) and result.keys() <= {"content", "isError"}:
        raise UpstreamMcpError("upstream MCP tool returned no JSON content")
    return result


def _init_payload() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "alloc-context-bridge", "version": "1"},
        },
        "id": 1,
    }


def _tools_call_payload(*, tool: str, arguments: dict[str, Any], request_id: int) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }


class UpstreamMcpClient:
    def __init__(self, user: UserConfig) -> None:
        self._url = user.upstream.rstrip("/")
        self._initialized = False
        self._request_id = 1
        self._session = None
        self._http_client = None
        try:
            self._payer_key = resolve_payer_private_key(user)
        except PayerKeyError as exc:
            raise UpstreamPaymentRequired(str(exc)) from exc

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._payer_key:
            raise UpstreamPaymentRequired("x402 payer private key is not configured")
        self._ensure_session()
        payload = _tools_call_payload(
            tool=name,
            arguments=dict(arguments or {}),
            request_id=self._next_id(),
        )
        response = self._session.post(
            self._url,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=120,
        )
        if not response.ok:
            raise UpstreamMcpError(
                f"upstream MCP HTTP {response.status_code}: {response.text[:400]}"
            )
        return _unwrap_tool_result(response.json())

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _ensure_session(self) -> None:
        if self._session is not None:
            return
        try:
            from eth_account import Account
            from x402 import x402ClientSync
            from x402.http import x402HTTPClientSync
            from x402.http.clients import x402_requests
            from x402.mechanisms.evm import EthAccountSigner
            from x402.mechanisms.evm.exact.register import register_exact_evm_client
        except ImportError as exc:
            raise UpstreamPaymentRequired(
                "Bridge upstream requires hosted extras: pip install 'alloc-context[hosted]'"
            ) from exc

        account = Account.from_key(self._payer_key)
        client = x402ClientSync()
        register_exact_evm_client(client, EthAccountSigner(account))
        self._http_client = x402HTTPClientSync(client)
        self._session = x402_requests(self._http_client)
        self._session.__enter__()
        init_response = self._session.post(
            self._url,
            json=_init_payload(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=60,
        )
        if not init_response.ok:
            raise UpstreamMcpError(
                f"upstream MCP initialize failed: HTTP {init_response.status_code}"
            )
        self._initialized = True

    def close(self) -> None:
        if self._session is not None:
            self._session.__exit__(None, None, None)
            self._session = None


def call_upstream_tool(
    user: UserConfig,
    name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not user.uses_upstream():
        raise UpstreamMcpError("upstream calls require bridge mode (not self_host)")
    client = UpstreamMcpClient(user)
    try:
        return client.call_tool(name, arguments=arguments)
    except UpstreamPaymentRequired:
        return upstream_payment_required()
    finally:
        client.close()
