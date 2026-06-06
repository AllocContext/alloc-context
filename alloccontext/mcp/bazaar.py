from __future__ import annotations

import os
from typing import Any

from x402.extensions.bazaar import (
    DeclareMcpDiscoveryConfig,
    OutputConfig,
    declare_discovery_extension,
    declare_mcp_discovery_extension,
)

from alloccontext.mcp.tool_catalog import (
    MCP_SERVER_PROMPTS,
    MCP_SERVER_RESOURCES,
    MCP_TOOL_NAMES,
    MCP_TOOL_SPECS,
    mcp_tool_specs,
    server_card_tool_entry,
)

SERVICE_NAME = "AllocContext"
OFFICIAL_HOSTED_MCP_URL = "https://mcp.alloc-context.com/mcp"
USE_DOCS_PATH = "docs/USE.md"

PRIVACY_COMPACT_COPY = (
    "Privacy: nothing stored. One-time read-only fetch. Pass-through only — "
    "your keys, wallet address, theses, and portfolio never persist on our "
    "servers."
)

PRIVACY_PILLAR_MARKERS = (
    "nothing stored",
    "one-time read-only",
    "pass-through only",
)

LICENSE_DISCOVERY_LINE = (
    "Source-available (Elastic License 2.0). Self-host friendly. Official hosted "
    f"MCP only at {OFFICIAL_HOSTED_MCP_URL} — see {USE_DOCS_PATH}."
)

LICENSE_MARKERS = (
    "elastic license",
    "self-host",
    USE_DOCS_PATH.lower(),
    OFFICIAL_HOSTED_MCP_URL.lower(),
)

SERVICE_TITLE = (
    "AllocContext — portfolio-aware crypto context for agents (MCP + x402)"
)
# CDP Bazaar indexes service_name (≤32 chars) and up to five tags from payments.
BAZAAR_SERVICE_NAME = "AllocContext portfolio MCP"
SERVICE_TAGS = (
    "crypto",
    "cryptocurrency",
    "bitcoin",
    "btc",
    "ethereum",
    "eth",
    "holdings",
    "portfolio",
    "allocation",
    "rebalance",
    "sentiment",
    "macro",
    "coinbase",
    "kraken",
    "agent-tools",
    "mcp",
    "x402",
)
BAZAAR_INDEX_TAGS = (
    "crypto",
    "cryptocurrency",
    "portfolio",
    "holdings",
    "btc",
)

DISCOVERY_KEYWORD_MARKERS = (
    "crypto",
    "cryptocurrency",
    "digital assets",
    "crypto portfolio",
    "portfolio allocation",
    "portfolio context",
    "allocation drift",
    "rebalance plan",
    "fear and greed",
    "etf flows",
    "holdings",
    "holdings-scoped",
    "coinbase",
    "kraken",
    "wallet",
    "on-chain",
    "market context",
    "sentiment",
)

LISTING_DESCRIPTION = (
    "Portfolio-aware crypto context for AI agents: discover holdings and "
    "holdings-scoped market, sentiment, macro, and regime; optional allocation "
    "analysis and rebalance math. Fused backdrop (Fear & Greed, Kalshi, ETF "
    "flows), optional live portfolio reads (CEX keys or public EVM wallet). "
    "Structured "
    "JSON only — no LLM. "
    f"{PRIVACY_COMPACT_COPY} "
    "Source-available (Elastic License 2.0); self-host friendly; official hosted "
    f"MCP at {OFFICIAL_HOSTED_MCP_URL} — see {USE_DOCS_PATH}."
)

def smoke_tool_arguments(tool_name: str) -> dict[str, Any]:
    """Example args for paid smoke / re-index scripts (hosted-safe defaults)."""
    from datetime import datetime, timedelta, timezone

    for spec in MCP_TOOL_SPECS:
        if spec["tool_name"] != tool_name:
            continue
        args = dict(spec["example"])
        now = datetime.now(timezone.utc)
        if tool_name == "get_context_at":
            args["as_of"] = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            args["match"] = "at_or_before"
            args.setdefault("scope", "daily")
        elif tool_name == "get_context_delta":
            # Hosted ingest keeps recent hourly snapshots; 2h back finds a prior point.
            prior = now - timedelta(hours=2)
            args["prior_as_of"] = prior.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            args.setdefault("scope", "daily")
        return args
    raise KeyError(f"unknown MCP tool: {tool_name}")


def public_mcp_url(*, base_url: str, mcp_path: str) -> str:
    return f"{base_url.rstrip('/')}{mcp_path}"


def resolve_public_base_url() -> str | None:
    for key in ("X402_PUBLIC_URL", "ALLOC_CONTEXT_MCP_PUBLIC_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value.rstrip("/")
    return None


def build_mcp_tool_extensions() -> dict[str, dict[str, Any]]:
    """Per-tool Bazaar MCP extensions keyed by tool name."""
    extensions: dict[str, dict[str, Any]] = {}
    for spec in MCP_TOOL_SPECS:
        extensions[spec["tool_name"]] = declare_mcp_discovery_extension(
            DeclareMcpDiscoveryConfig(
                tool_name=spec["tool_name"],
                description=spec["description"],
                transport="streamable-http",
                input_schema=spec["input_schema"],
                example=spec["example"],
                output=OutputConfig(example=spec["output_example"]),
            )
        )
    return extensions


def build_http_route_extensions() -> dict[str, Any]:
    """Bazaar extension for the paid POST /mcp streamable HTTP endpoint."""
    primary = MCP_TOOL_SPECS[0]
    return declare_discovery_extension(
        input={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": primary["tool_name"],
                "arguments": primary["example"],
            },
            "id": 1,
        },
        input_schema={
            "type": "object",
            "properties": {
                "jsonrpc": {"type": "string", "const": "2.0"},
                "method": {
                    "type": "string",
                    "description": "MCP JSON-RPC method (e.g. tools/call).",
                },
                "params": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": list(MCP_TOOL_NAMES),
                            "description": (
                                "AllocContext tool: get_market_context, "
                                "get_context_bundle, get_rebalance_plan, "
                                "get_portfolio_state, check_allocation_band, "
                                "get_context_at, get_context_delta, or "
                                "check_allocation_bands."
                            ),
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Tool-specific arguments object.",
                        },
                    },
                    "required": ["name"],
                },
                "id": {"type": ["integer", "string"]},
            },
            "required": ["jsonrpc", "method", "params"],
        },
        body_type="json",
        output=OutputConfig(
            example={
                "jsonrpc": "2.0",
                "id": 1,
                "result": primary["output_example"],
            }
        ),
    )


def build_llms_txt(
    *,
    public_url: str,
    mcp_path: str,
    accepted_stables: tuple[str, ...] = ("USDC", "EURC"),
) -> str:
    endpoint = public_mcp_url(base_url=public_url, mcp_path=mcp_path)
    tool_lines = "\n".join(
        f"- `{spec['tool_name']}` — {spec['description']}" for spec in MCP_TOOL_SPECS
    )
    return f"""# {SERVICE_TITLE}

{LISTING_DESCRIPTION}

## Privacy

Nothing stored. One-time read-only fetch. Pass-through only — your keys, wallet
address, and portfolio never persist on our servers.

## License

{LICENSE_DISCOVERY_LINE}

## Paid MCP (x402, Base stablecoins)

- Endpoint: `{endpoint}`
- Transport: streamable HTTP (`POST {mcp_path}`)
- Health: `{public_url.rstrip('/')}/health` (free)
- Payment: x402 exact scheme on Base; payer picks one of
  **{", ".join(accepted_stables)}** (USD-pegged; bridge to Base first).
- Pricing: **$0.02** cached context/math; **$0.05** live ingest or live portfolio.

## Tools

{tool_lines}

## Search keywords

bitcoin, ethereum, btc, eth, crypto, cryptocurrency, digital assets, altcoin,
stablecoin, crypto portfolio, portfolio allocation, portfolio context, holdings,
holdings-scoped, coinbase, kraken, wallet, on-chain, market context, market data, sentiment,
macro calendar, etf flows, allocation drift, allocation bands, rebalance plan,
fear and greed, fear greed index, nav, agent tools, ai agents, mcp, x402,
model context protocol, context bundle

## Examples

Redacted tool JSON samples (evaluate before paying):
https://github.com/AllocContext/alloc-context/blob/main/docs/examples.md
"""


def build_well_known_x402(
    *,
    public_url: str,
    mcp_path: str,
    pay_to: str,
    price_light: str = "$0.02",
    price_heavy: str = "$0.05",
    network: str = "eip155:84532",
    accepted_stables: tuple[str, ...] = ("USDC", "EURC"),
) -> dict[str, Any]:
    endpoint = public_mcp_url(base_url=public_url, mcp_path=mcp_path)
    return {
        "name": SERVICE_NAME,
        "title": SERVICE_TITLE,
        "description": LISTING_DESCRIPTION,
        "tags": list(SERVICE_TAGS),
        "resources": [
            {
                "url": endpoint,
                "type": "http",
                "description": LISTING_DESCRIPTION,
                "tools": [
                    {
                        "name": spec["tool_name"],
                        "description": spec["description"],
                        "inputSchema": spec["input_schema"],
                    }
                    for spec in MCP_TOOL_SPECS
                ],
            }
        ],
        "payment": {
            "scheme": "exact",
            "payTo": pay_to,
            "pricing": {
                "cached_context_and_math": price_light,
                "live_ingest_or_portfolio": price_heavy,
                "network": network,
                "assets": list(accepted_stables),
                "note": (
                    "Payer chooses one listed stable on Base; amounts are "
                    "USD-pegged per call tier."
                ),
            },
        },
    }


def build_mcp_server_card(*, version: str) -> dict[str, Any]:
    """Smithery static server card (SEP-1649) — free metadata when POST /mcp is x402."""
    return {
        "serverInfo": {
            "name": SERVICE_TITLE,
            "version": version,
            "description": LISTING_DESCRIPTION,
        },
        "authentication": {
            "required": True,
            "schemes": ["x402"],
            "description": (
                "x402 exact payment on Base mainnet (USDC or EURC) per tool call; "
                "see /.well-known/x402.json for pricing."
            ),
        },
        "tools": [server_card_tool_entry(spec) for spec in MCP_TOOL_SPECS],
        "resources": list(MCP_SERVER_RESOURCES),
        "prompts": list(MCP_SERVER_PROMPTS),
    }
