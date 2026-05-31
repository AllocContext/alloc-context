from __future__ import annotations

import os
from typing import Any

from alloccontext.config import load_config
from alloccontext.mcp import handlers
from alloccontext.mcp.instructions import PRODUCT_INSTRUCTIONS, REBALANCE_HINT_GUIDE
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
        instructions=PRODUCT_INSTRUCTIONS,
    )

    @mcp.tool(
        name="get_context_bundle",
        description=(
            "Full ContextBundle JSON: portfolio holdings, market, sentiment, "
            "macro, regime hints, and delta vs the prior saved snapshot. Optional "
            "assets filter (default BTC, ETH). Optional target_pct and band attach "
            "allocation_analysis (opt-in drift math). freshness=cached uses the "
            "local ingest DB; freshness=live runs ingest first."
        ),
    )
    def get_context_bundle(
        scope: str = "daily",
        freshness: str = "cached",
        assets: list[str] | None = None,
        target_pct: dict[str, float] | None = None,
        band: float | None = None,
    ) -> dict[str, Any]:
        """Return the full deterministic context bundle for daily or weekly scope."""
        validated_scope = handlers.validate_scope(scope)
        validated_freshness = handlers.validate_freshness(freshness)
        conn = connect(config.paths.db)
        try:
            return handlers.get_context_bundle(
                conn,
                config,
                scope=validated_scope,
                freshness=validated_freshness,
                assets=assets,
                target_pct=target_pct,
                band=band,
            )
        finally:
            conn.close()

    @mcp.tool(
        name="get_market_context",
        description=(
            "Fused market backdrop: sentiment (Fear & Greed, Kalshi), macro events, "
            "FRED indicators, ETF flows, and market breadth. Optional assets filter "
            "(default BTC, ETH). freshness=cached uses the local ingest DB; "
            "freshness=live runs ingest first (requires ingest API keys on the host)."
        ),
    )
    def get_market_context(
        scope: str = "daily",
        freshness: str = "cached",
        assets: list[str] | None = None,
    ) -> dict[str, Any]:
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
                assets=assets,
            )
        finally:
            conn.close()

    @mcp.tool(
        name="get_rebalance_plan",
        description=(
            "USD deltas and exchange-style move lines to reach a target BTC/ETH/CASH "
            "split. Requires allocation_pct, target_pct, and nav_usd. Optional band "
            "returns a band_check block alongside the plan. exchange=kraken|coinbase "
            "adjusts move wording."
        ),
    )
    def get_rebalance_plan(
        allocation_pct: dict[str, float],
        target_pct: dict[str, float],
        nav_usd: float,
        exchange: str = "kraken",
        band: float | None = None,
    ) -> dict[str, Any]:
        """Compute rebalance plan from current allocation and NAV."""
        return handlers.get_rebalance_plan(
            allocation_pct,
            target_pct,
            nav_usd,
            exchange=exchange,
            band=band,
        )

    @mcp.tool(
        name="get_portfolio_state",
        description=(
            "Live portfolio NAV, holdings[], and band weights from read-only "
            "exchange credentials passed in the request. Optional target_pct "
            "attaches allocation_analysis. Credentials are never stored. "
            "Supports kraken and coinbase."
        ),
    )
    def get_portfolio_state(
        exchange: str,
        api_key: str,
        api_secret: str,
        target_pct: dict[str, float] | None = None,
        band: float | None = None,
    ) -> dict[str, Any]:
        """Fetch live portfolio state using caller-supplied read-only API keys."""
        return handlers.get_portfolio_state(
            config,
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            target_pct=target_pct,
            band=band,
        )

    @mcp.tool(
        name="check_allocation_band",
        description=(
            "Check whether BTC/ETH/CASH band weights are outside a drift band vs "
            "target_pct and return hint (within_band, consider_rebalance, etc.). "
            "All three inputs are required. For bundle drift, pass target_pct on "
            "get_context_bundle to attach allocation_analysis."
        ),
    )
    def check_allocation_band(
        allocation_pct: dict[str, float],
        target_pct: dict[str, float],
        band: float = 0.15,
    ) -> dict[str, Any]:
        """Evaluate allocation drift against band width (default 0.15 = 15%)."""
        return handlers.check_band(allocation_pct, target_pct, band)

    @mcp.tool(
        name="get_context_at",
        description=(
            "Load a saved ContextBundle snapshot from ingest history. "
            "as_of is an ISO timestamp; match=at_or_before returns the latest "
            "snapshot on or before that time."
        ),
    )
    def get_context_at(
        as_of: str,
        scope: str = "daily",
        match: str = "at_or_before",
        assets: list[str] | None = None,
        target_pct: dict[str, float] | None = None,
        band: float | None = None,
    ) -> dict[str, Any]:
        validated_scope = handlers.validate_scope(scope)
        if match not in ("exact", "at_or_before"):
            raise ValueError("match must be 'exact' or 'at_or_before'")
        conn = connect(config.paths.db)
        try:
            return handlers.get_context_at(
                conn,
                config,
                scope=validated_scope,
                as_of=as_of,
                match=match,  # type: ignore[arg-type]
                assets=assets,
                target_pct=target_pct,
                band=band,
            )
        finally:
            conn.close()

    @mcp.tool(
        name="get_context_delta",
        description=(
            "Compare two ContextBundle snapshots and return notable_shifts. "
            "prior_as_of is required; omit current_as_of for latest live bundle."
        ),
    )
    def get_context_delta(
        prior_as_of: str,
        scope: str = "daily",
        current_as_of: str | None = None,
        assets: list[str] | None = None,
    ) -> dict[str, Any]:
        validated_scope = handlers.validate_scope(scope)
        conn = connect(config.paths.db)
        try:
            return handlers.get_context_delta(
                conn,
                config,
                scope=validated_scope,
                prior_as_of=prior_as_of,
                current_as_of=current_as_of,
                assets=assets,
            )
        finally:
            conn.close()

    @mcp.tool(
        name="check_allocation_bands",
        description=(
            "Evaluate allocation drift against multiple target_pct/band "
            "scenarios in one call. Each scenario needs target_pct; optional "
            "name and band (default 0.15)."
        ),
    )
    def check_allocation_bands(
        allocation_pct: dict[str, float],
        scenarios: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return handlers.check_allocation_bands(allocation_pct, scenarios)

    schema_v1_path = (
        __import__("pathlib").Path(__file__).resolve().parent.parent.parent
        / "schemas"
        / "context-bundle.v1.json"
    )
    schema_v2_path = schema_v1_path.with_name("context-bundle.v2.json")

    @mcp.resource("context-bundle://schema/v1")
    def context_bundle_schema_v1() -> str:
        """Legacy ContextBundle JSON Schema (pre-holdings)."""
        return schema_v1_path.read_text(encoding="utf-8")

    @mcp.resource("context-bundle://schema/v2")
    def context_bundle_schema_v2() -> str:
        """ContextBundle JSON Schema (portfolio-first, optional allocation_analysis)."""
        return schema_v2_path.read_text(encoding="utf-8")

    @mcp.resource("alloc-context://tools/rebalance-hints")
    def rebalance_hint_guide() -> str:
        """Meaning of rebalance_hint codes in allocation_analysis."""
        return REBALANCE_HINT_GUIDE

    return mcp


def run_stdio(*, config_path: str | None = None) -> None:
    mcp = create_server(config_path=config_path)
    mcp.run(transport="stdio")


def main() -> None:
    run_stdio()


if __name__ == "__main__":
    main()
