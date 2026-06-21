from __future__ import annotations

from typing import Any

PRIVACY_NOTE_LONG = (
    "We do not store your portfolio data, exchange keys, or x402 payer key. "
    "Live reads are read-only and scoped to a single request. Pass-through only "
    "on your device."
)

DEFAULT_USER_CONFIG_PATH = "~/.config/alloc-context/user.yaml"


def setup_block(
    *,
    feature: str,
    path: str,
    reason: str,
    message: str,
    steps: list[str],
    docs: str = "docs/user-config.md",
    example: dict[str, Any] | None = None,
    include_privacy: bool = False,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "feature": feature,
        "path": path,
        "config_path": DEFAULT_USER_CONFIG_PATH,
        "docs": docs,
        "steps": steps,
    }
    if example:
        block["example"] = example
    if include_privacy:
        block["privacy_note"] = PRIVACY_NOTE_LONG
    return block


def unavailable(
    *,
    reason: str,
    message: str,
    setup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "reason": reason,
        "message": message,
    }
    if setup is not None:
        payload["setup"] = setup
    return payload


def portfolio_not_configured(*, path: str = "bridge") -> dict[str, Any]:
    return unavailable(
        reason="portfolio_not_configured",
        message="Add read-only exchange credentials to user config for portfolio.",
        setup=setup_block(
            feature="portfolio",
            path=path,
            reason="portfolio_not_configured",
            message="Add read-only exchange credentials to user config for portfolio.",
            include_privacy=True,
            steps=[
                f"Create {DEFAULT_USER_CONFIG_PATH}",
                "Set exchanges.primary to coinbase or kraken",
                "Add read-only api_key and api_secret under that exchange",
                "Restart the alloc-context MCP bridge",
            ],
            example={
                "exchanges": {
                    "primary": "coinbase",
                    "coinbase": {"api_key": "...", "api_secret": "..."},
                }
            },
        ),
    )


def bridge_upstream_retired(*, path: str = "bridge") -> dict[str, Any]:
    return unavailable(
        reason="upstream_retired",
        message="Hosted MCP upstream is retired. Use self-host stdio MCP.",
        setup=setup_block(
            feature="bridge_upstream",
            path=path,
            reason="upstream_retired",
            message="Hosted MCP upstream is retired. Use self-host stdio MCP.",
            docs="docs/cursor-mcp.md",
            steps=[
                "Remove or rename ~/.config/alloc-context/user.yaml",
                "Use alloc-context mcp --config config/config.yaml in mcp.json",
                "See docs/cursor-mcp.md and docs/self-hosting.md",
            ],
        ),
    )


def upstream_payment_required(*, path: str = "bridge") -> dict[str, Any]:
    return unavailable(
        reason="upstream_payment_required",
        message="Configure an x402 payer wallet for a self-hosted HTTP MCP URL.",
        setup=setup_block(
            feature="x402_payment",
            path=path,
            reason="upstream_payment_required",
            message="Configure an x402 payer wallet for a self-hosted HTTP MCP URL.",
            include_privacy=True,
            steps=[
                "Fund a Base wallet with USDC or EURC",
                "Set EVM_PRIVATE_KEY or x402.payer_private_key_file in user config",
                "Ensure payer address differs from hosted payTo",
            ],
            example={
                "x402": {
                    "payer_private_key_env": "EVM_PRIVATE_KEY",
                }
            },
        ),
    )


def allocation_not_configured(*, path: str = "bridge") -> dict[str, Any]:
    return unavailable(
        reason="allocation_not_configured",
        message="Provide target_allocation in user config or on the tool call.",
        setup=setup_block(
            feature="allocation_analysis",
            path=path,
            reason="allocation_not_configured",
            message="Provide target_allocation in user config or on the tool call.",
            include_privacy=False,
            steps=[
                f"Add target_allocation to {DEFAULT_USER_CONFIG_PATH}, or",
                "Pass target_pct on the tool call",
            ],
            example={
                "target_allocation": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.00},
                "band": 0.15,
            },
        ),
    )
