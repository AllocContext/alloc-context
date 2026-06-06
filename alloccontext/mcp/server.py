from __future__ import annotations

import os
from typing import Any

from alloccontext.config import load_config
from alloccontext.mcp import handlers
from alloccontext.mcp.instructions import PRODUCT_INSTRUCTIONS, REBALANCE_HINT_GUIDE
from alloccontext.mcp.tool_catalog import (
    tool_description,
    tool_mcp_annotations,
    tool_title,
)
from alloccontext.mcp.tool_fields import (
    AllocationPct,
    ApiKey,
    ApiSecret,
    AsOf,
    Assets,
    BandDefault,
    BandOptional,
    CurrentAsOf,
    Exchange,
    ExchangeKrakenDefault,
    Freshness,
    MatchMode,
    NavUsd,
    OptionalTargetPct,
    OptionalTheses,
    PriorAsOf,
    Scenarios,
    Scope,
    TargetPct,
    WalletAddress,
)
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


def _tool_hints(tool_name: str):
    return tool_mcp_annotations(tool_name)


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
        title=tool_title("get_context_bundle"),
        annotations=_tool_hints("get_context_bundle"),
        description=tool_description("get_context_bundle"),
    )
    def get_context_bundle(
        scope: Scope = "daily",
        freshness: Freshness = "cached",
        assets: Assets = None,
        target_pct: OptionalTargetPct = None,
        band: BandOptional = None,
        theses: OptionalTheses = None,
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
                theses=theses,
            )
        finally:
            conn.close()

    @mcp.tool(
        name="get_market_context",
        title=tool_title("get_market_context"),
        annotations=_tool_hints("get_market_context"),
        description=tool_description("get_market_context"),
    )
    def get_market_context(
        scope: Scope = "daily",
        freshness: Freshness = "cached",
        assets: Assets = None,
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
        title=tool_title("get_rebalance_plan"),
        annotations=_tool_hints("get_rebalance_plan"),
        description=tool_description("get_rebalance_plan"),
    )
    def get_rebalance_plan(
        allocation_pct: AllocationPct,
        target_pct: TargetPct,
        nav_usd: NavUsd,
        exchange: ExchangeKrakenDefault = "kraken",
        band: BandOptional = None,
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
        title=tool_title("get_portfolio_state"),
        annotations=_tool_hints("get_portfolio_state"),
        description=tool_description("get_portfolio_state"),
    )
    def get_portfolio_state(
        exchange: Exchange,
        api_key: ApiKey = "",
        api_secret: ApiSecret = "",
        wallet_address: WalletAddress = None,
        target_pct: OptionalTargetPct = None,
        band: BandOptional = None,
    ) -> dict[str, Any]:
        """Fetch live portfolio from exchange keys or a public EVM wallet address."""
        return handlers.get_portfolio_state(
            config,
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            wallet_address=wallet_address,
            target_pct=target_pct,
            band=band,
        )

    @mcp.tool(
        name="check_allocation_band",
        title=tool_title("check_allocation_band"),
        annotations=_tool_hints("check_allocation_band"),
        description=tool_description("check_allocation_band"),
    )
    def check_allocation_band(
        allocation_pct: AllocationPct,
        target_pct: TargetPct,
        band: BandDefault = 0.15,
    ) -> dict[str, Any]:
        """Evaluate allocation drift against band width (default 0.15 = 15%)."""
        return handlers.check_band(allocation_pct, target_pct, band)

    @mcp.tool(
        name="get_context_at",
        title=tool_title("get_context_at"),
        annotations=_tool_hints("get_context_at"),
        description=tool_description("get_context_at"),
    )
    def get_context_at(
        as_of: AsOf,
        scope: Scope = "daily",
        match: MatchMode = "at_or_before",
        assets: Assets = None,
        target_pct: OptionalTargetPct = None,
        band: BandOptional = None,
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
        title=tool_title("get_context_delta"),
        annotations=_tool_hints("get_context_delta"),
        description=tool_description("get_context_delta"),
    )
    def get_context_delta(
        prior_as_of: PriorAsOf,
        scope: Scope = "daily",
        current_as_of: CurrentAsOf = None,
        assets: Assets = None,
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
        title=tool_title("check_allocation_bands"),
        annotations=_tool_hints("check_allocation_bands"),
        description=tool_description("check_allocation_bands"),
    )
    def check_allocation_bands(
        allocation_pct: AllocationPct,
        scenarios: Scenarios,
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
