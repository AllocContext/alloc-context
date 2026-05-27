from __future__ import annotations

import os
from typing import Any

from alloccontext.config import load_config
from alloccontext.mcp import handlers
from alloccontext.store.db import connect


def _transport_security_settings(*, host: str):
    from urllib.parse import urlparse

    from mcp.server.transport_security import TransportSecuritySettings

    from alloccontext.mcp.bazaar import resolve_public_base_url

    public = resolve_public_base_url()
    if not public:
        return None

    parsed = urlparse(public if "://" in public else f"https://{public}")
    hostname = parsed.hostname
    if not hostname:
        return None

    scheme = parsed.scheme or "https"
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
            hostname,
            f"{hostname}:*",
        ],
        allowed_origins=[
            f"{scheme}://{hostname}:*",
            public.rstrip("/"),
        ],
    )


def _require_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "MCP support requires the mcp package: pip install 'alloc-context[mcp]'"
        ) from exc
    return FastMCP


def create_server(
    *,
    config_path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    stateless_http: bool = True,
):
    FastMCP = _require_mcp()
    if config_path:
        os.environ.setdefault("ALLOC_CONTEXT_CONFIG", config_path)

    config = load_config(config_path)

    mcp = FastMCP(
        "alloc-context",
        json_response=True,
        host=host,
        port=port,
        stateless_http=stateless_http,
        transport_security=_transport_security_settings(host=host),
        instructions=(
            "BTC/ETH allocation context: fused market backdrop from cached ingest, "
            "USD rebalance moves, and allocation band checks. Facts only — no LLM."
        ),
    )

    @mcp.tool(
        name="get_market_context",
        description=(
            "Fused market backdrop: sentiment (Fear & Greed, Kalshi), macro events, "
            "FRED indicators, ETF flows, and market breadth. freshness=cached uses the "
            "local ingest DB; freshness=live runs ingest first (requires operator keys)."
        ),
    )
    def get_market_context(scope: str = "daily", freshness: str = "cached") -> dict[str, Any]:
        """Return ContextBundle subset for daily or weekly scope."""
        validated_scope = handlers.validate_scope(scope)
        validated_freshness = handlers.validate_freshness(freshness)
        conn = connect(config.paths.db)
        try:
            return handlers.get_market_context(
                conn,
                config,
                scope=validated_scope,
                freshness=validated_freshness,
            )
        finally:
            conn.close()

    @mcp.tool(
        name="get_rebalance_plan",
        description=(
            "USD deltas and exchange-style move lines to reach a target BTC/ETH/CASH "
            "split. Pure math — no exchange keys."
        ),
    )
    def get_rebalance_plan(
        allocation_pct: dict[str, float],
        target_pct: dict[str, float],
        nav_usd: float,
    ) -> dict[str, Any]:
        """Compute rebalance plan from current allocation and NAV."""
        return handlers.get_rebalance_plan(allocation_pct, target_pct, nav_usd)

    @mcp.tool(
        name="check_allocation_band",
        description=(
            "Check whether BTC/ETH/CASH allocation is outside a drift band vs "
            "target and return hint (within_band, consider_rebalance, etc.)."
        ),
    )
    def check_allocation_band(
        allocation_pct: dict[str, float],
        target_pct: dict[str, float],
        band: float = 0.15,
    ) -> dict[str, Any]:
        """Evaluate allocation drift against band width (default 0.15 = 15%)."""
        return handlers.check_band(allocation_pct, target_pct, band)

    return mcp


def run_stdio(*, config_path: str | None = None) -> None:
    mcp = create_server(config_path=config_path)
    mcp.run(transport="stdio")


def main() -> None:
    run_stdio()


if __name__ == "__main__":
    main()
