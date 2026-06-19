from __future__ import annotations

from typing import Any

from alloccontext.mcp import handlers
from alloccontext.mcp.bridge_portfolio import (
    attach_assets_scope,
    attach_bridge_expectation_review,
    bridge_upstream_ready,
    build_bridge_expectation_review_payload,
    build_upstream_context_args,
    default_bridge_app_config,
    fetch_user_portfolio,
    merge_assets_omitted,
    merge_portfolio_into_bundle,
    resolve_bridge_assets,
    strip_upstream_allocation_regime,
)
from alloccontext.mcp.setup import allocation_not_configured, upstream_payment_required
from alloccontext.mcp.upstream import call_upstream_tool
from alloccontext.user_config import (
    UserConfig,
    load_user_config,
    resolve_user_config_path,
)


from alloccontext.mcp.instructions import PRODUCT_INSTRUCTIONS
from alloccontext.mcp.tool_catalog import (
    tool_description,
    tool_mcp_annotations,
    tool_title,
)


def _effective_target_pct(
    user: UserConfig,
    target_pct: dict[str, float] | None,
) -> dict[str, float] | None:
    if target_pct is not None:
        return target_pct
    return user.target_allocation


def _effective_band(user: UserConfig, band: float | None) -> float | None:
    if band is not None:
        return band
    return user.band


def _effective_theses(
    user: UserConfig,
    theses: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if theses is not None:
        return theses
    return user.theses


def _fetch_upstream_baseline(user: UserConfig, *, scope: str, recorded_at: str) -> dict[str, Any]:
    return call_upstream_tool(
        user,
        "get_context_at",
        {
            "scope": scope,
            "as_of": recorded_at,
            "match": "thesis_baseline",
        },
    )


def _fetch_upstream_checkpoint(user: UserConfig, *, scope: str, as_of: str) -> dict[str, Any]:
    return call_upstream_tool(
        user,
        "get_context_at",
        {
            "scope": scope,
            "as_of": as_of,
            "match": "at_or_before",
        },
    )


def _bridge_tool_meta(tool_name: str) -> dict[str, Any]:
    return {
        "name": tool_name,
        "title": tool_title(tool_name),
        "annotations": tool_mcp_annotations(tool_name),
        "description": tool_description(tool_name),
    }


def create_bridge_server(user: UserConfig):
    from alloccontext.mcp.server import _require_mcp

    FastMCP = _require_mcp()
    bridge_config = default_bridge_app_config()

    mcp = FastMCP(
        "alloc-context",
        json_response=True,
        stateless_http=True,
        instructions=PRODUCT_INSTRUCTIONS,
    )

    @mcp.tool(**_bridge_tool_meta("get_market_context"))
    def get_market_context(
        scope: str = "daily",
        freshness: str = "cached",
        assets: list[str] | None = None,
    ) -> dict[str, Any]:
        validated_scope = handlers.validate_scope(scope)
        validated_freshness = handlers.validate_freshness(freshness)
        portfolio: dict[str, Any] | None = None
        if (
            (assets is None or len(assets) == 0)
            and user.primary_exchange_credentials() is not None
            and bridge_upstream_ready(user)
        ):
            portfolio = fetch_user_portfolio(user, bridge_config)
        effective_assets, assets_scope = resolve_bridge_assets(
            user,
            bridge_config,
            assets,
            portfolio=portfolio,
        )
        payload = call_upstream_tool(
            user,
            "get_market_context",
            build_upstream_context_args(
                scope=validated_scope,
                freshness=validated_freshness,
                assets=effective_assets,
            ),
        )
        if payload.get("reason") == "upstream_payment_required":
            return payload
        if portfolio is not None:
            payload = merge_assets_omitted(payload, portfolio)
        return attach_assets_scope(payload, assets_scope)

    @mcp.tool(**_bridge_tool_meta("get_context_bundle"))
    def get_context_bundle(
        scope: str = "daily",
        freshness: str = "cached",
        assets: list[str] | None = None,
        target_pct: dict[str, float] | None = None,
        band: float | None = None,
        theses: list[dict[str, Any]] | None = None,
        expectation_replay: bool = False,
    ) -> dict[str, Any]:
        validated_scope = handlers.validate_scope(scope)
        validated_freshness = handlers.validate_freshness(freshness)
        if not bridge_upstream_ready(user):
            if _effective_theses(user, theses):
                return upstream_payment_required()
            effective_assets, _assets_scope = resolve_bridge_assets(
                user,
                bridge_config,
                assets,
                portfolio=None,
            )
            return call_upstream_tool(
                user,
                "get_context_bundle",
                build_upstream_context_args(
                    scope=validated_scope,
                    freshness=validated_freshness,
                    assets=effective_assets,
                ),
            )
        portfolio = fetch_user_portfolio(
            user,
            bridge_config,
            target_pct=_effective_target_pct(user, target_pct),
            band=_effective_band(user, band),
        )
        effective_assets, assets_scope = resolve_bridge_assets(
            user,
            bridge_config,
            assets,
            portfolio=portfolio,
        )
        bundle = call_upstream_tool(
            user,
            "get_context_bundle",
            build_upstream_context_args(
                scope=validated_scope,
                freshness=validated_freshness,
                assets=effective_assets,
            ),
        )
        if bundle.get("available") is False:
            return bundle
        merged = merge_portfolio_into_bundle(bundle, portfolio)
        merged = strip_upstream_allocation_regime(merged)
        merged = merge_assets_omitted(merged, portfolio)
        merged = attach_bridge_expectation_review(
            user=user,
            bundle=merged,
            scope=validated_scope,
            theses=_effective_theses(user, theses),
            target_pct=_effective_target_pct(user, target_pct),
            band=_effective_band(user, band),
            fetch_baseline=lambda **kwargs: _fetch_upstream_baseline(
                user,
                scope=kwargs["scope"],
                recorded_at=kwargs["recorded_at"],
            ),
            expectation_replay=expectation_replay,
            fetch_checkpoint=lambda **kwargs: _fetch_upstream_checkpoint(
                user,
                scope=kwargs["scope"],
                as_of=kwargs["as_of"],
            ),
        )
        return attach_assets_scope(merged, assets_scope)

    @mcp.tool(**_bridge_tool_meta("get_expectation_review"))
    def get_expectation_review(
        scope: str = "daily",
        freshness: str = "cached",
        theses: list[dict[str, Any]] | None = None,
        target_pct: dict[str, float] | None = None,
        band: float | None = None,
        expectation_replay: bool = False,
    ) -> dict[str, Any]:
        validated_scope = handlers.validate_scope(scope)
        validated_freshness = handlers.validate_freshness(freshness)
        effective_theses = _effective_theses(user, theses)
        if not effective_theses:
            return {"available": False, "reason": "no_theses_supplied"}
        if not bridge_upstream_ready(user):
            return upstream_payment_required()
        portfolio = fetch_user_portfolio(
            user,
            bridge_config,
            target_pct=_effective_target_pct(user, target_pct),
            band=_effective_band(user, band),
        )
        effective_assets, _assets_scope = resolve_bridge_assets(
            user,
            bridge_config,
            None,
            portfolio=portfolio,
        )
        bundle = call_upstream_tool(
            user,
            "get_context_bundle",
            build_upstream_context_args(
                scope=validated_scope,
                freshness=validated_freshness,
                assets=effective_assets,
            ),
        )
        if bundle.get("available") is False:
            return bundle
        merged = merge_portfolio_into_bundle(bundle, portfolio)
        merged = strip_upstream_allocation_regime(merged)
        return build_bridge_expectation_review_payload(
            user=user,
            bundle=merged,
            scope=validated_scope,
            theses=effective_theses,
            target_pct=_effective_target_pct(user, target_pct),
            band=_effective_band(user, band),
            fetch_baseline=lambda **kwargs: _fetch_upstream_baseline(
                user,
                scope=kwargs["scope"],
                recorded_at=kwargs["recorded_at"],
            ),
            expectation_replay=expectation_replay,
            fetch_checkpoint=lambda **kwargs: _fetch_upstream_checkpoint(
                user,
                scope=kwargs["scope"],
                as_of=kwargs["as_of"],
            ),
        )

    @mcp.tool(**_bridge_tool_meta("get_portfolio_state"))
    def get_portfolio_state(
        exchange: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        target_pct: dict[str, float] | None = None,
        band: float | None = None,
    ) -> dict[str, Any]:
        from alloccontext.mcp.setup import portfolio_not_configured

        creds = user.primary_exchange_credentials()
        ex = (exchange or (creds.exchange_id if creds else "") or "").strip().lower()
        key = (api_key or (creds.api_key if creds else "") or "").strip()
        secret = (api_secret or (creds.api_secret if creds else "") or "").strip()
        if not ex or not key or not secret:
            return portfolio_not_configured()
        return handlers.get_portfolio_state(
            bridge_config,
            exchange=ex,
            api_key=key,
            api_secret=secret,
            target_pct=_effective_target_pct(user, target_pct),
            band=_effective_band(user, band),
        )

    @mcp.tool(**_bridge_tool_meta("get_rebalance_plan"))
    def get_rebalance_plan(
        allocation_pct: dict[str, float],
        target_pct: dict[str, float] | None = None,
        nav_usd: float = 0,
        exchange: str = "kraken",
        band: float | None = None,
    ) -> dict[str, Any]:
        effective_target = _effective_target_pct(user, target_pct)
        if effective_target is None:
            return allocation_not_configured()
        return handlers.get_rebalance_plan(
            allocation_pct,
            effective_target,
            nav_usd,
            exchange=exchange,
            band=_effective_band(user, band),
        )

    @mcp.tool(**_bridge_tool_meta("check_allocation_band"))
    def check_allocation_band(
        allocation_pct: dict[str, float],
        target_pct: dict[str, float] | None = None,
        band: float | None = None,
    ) -> dict[str, Any]:
        effective_target = _effective_target_pct(user, target_pct)
        if effective_target is None:
            return allocation_not_configured()
        effective_band = _effective_band(user, band) or 0.15
        return handlers.check_band(allocation_pct, effective_target, effective_band)

    @mcp.tool(**_bridge_tool_meta("check_allocation_bands"))
    def check_allocation_bands(
        allocation_pct: dict[str, float],
        scenarios: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return handlers.check_allocation_bands(allocation_pct, scenarios)

    @mcp.tool(**_bridge_tool_meta("get_context_at"))
    def get_context_at(
        as_of: str,
        scope: str = "daily",
        match: str = "at_or_before",
        assets: list[str] | None = None,
        target_pct: dict[str, float] | None = None,
        band: float | None = None,
    ) -> dict[str, Any]:
        validated_scope = handlers.validate_scope(scope)
        if match not in ("exact", "at_or_before", "thesis_baseline"):
            raise ValueError(
                "match must be 'exact', 'at_or_before', or 'thesis_baseline'"
            )
        args: dict[str, Any] = {
            "as_of": as_of,
            "scope": validated_scope,
            "match": match,
            "assets": assets,
        }
        effective_target = _effective_target_pct(user, target_pct)
        effective_band = _effective_band(user, band)
        if effective_target is not None:
            args["target_pct"] = effective_target
        if effective_band is not None:
            args["band"] = effective_band
        return call_upstream_tool(user, "get_context_at", args)

    @mcp.tool(**_bridge_tool_meta("get_context_delta"))
    def get_context_delta(
        prior_as_of: str,
        scope: str = "daily",
        current_as_of: str | None = None,
        assets: list[str] | None = None,
    ) -> dict[str, Any]:
        validated_scope = handlers.validate_scope(scope)
        args: dict[str, Any] = {
            "prior_as_of": prior_as_of,
            "scope": validated_scope,
            "assets": assets,
        }
        if current_as_of is not None:
            args["current_as_of"] = current_as_of
        return call_upstream_tool(user, "get_context_delta", args)

    return mcp


def run_bridge_stdio(*, user_config_path: str | None = None) -> None:
    path = resolve_user_config_path(user_config_path)
    user = load_user_config(path)
    if user.self_host:
        config_path = user.server_config
        if not config_path:
            import json
            import sys

            from alloccontext.mcp.setup import setup_block, unavailable

            payload = unavailable(
                reason="self_host_not_configured",
                message="self_host requires config path in user.yaml",
                setup=setup_block(
                    feature="self_host",
                    path="self_host",
                    reason="self_host_not_configured",
                    message="self_host requires config path in user.yaml",
                    steps=[
                        "Set self_host: true in user config",
                        "Set config: /path/to/config/config.yaml",
                    ],
                    docs="docs/self-hosting.md",
                ),
            )
            print(json.dumps(payload, indent=2), file=sys.stderr)
            raise SystemExit(1)
        from alloccontext.mcp.server import run_stdio

        run_stdio(config_path=config_path)
        return

    mcp = create_bridge_server(user)
    mcp.run(transport="stdio")


def run_mcp_stdio(*, config_path: str | None = None, user_config_path: str | None = None) -> None:
    if user_config_path is not None:
        run_bridge_stdio(user_config_path=user_config_path)
        return
    auto_path = resolve_user_config_path(None)
    if auto_path is not None:
        run_bridge_stdio(user_config_path=str(auto_path))
        return
    from alloccontext.mcp.server import run_stdio

    run_stdio(config_path=config_path)
