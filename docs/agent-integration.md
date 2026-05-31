# Agent integration (hosted MCP + x402)

Use the **production** AllocContext endpoint from agents, wallets, or Cursor
without running ingest locally. Payment is per-call x402 on Base mainnet.

> **Privacy:** nothing stored · one-time read-only · pass-through only — your
> keys and portfolio never persist on our servers.

> **License:** source-available ([Elastic License 2.0](../LICENSE)), self-host
> friendly. Official hosted MCP only at `https://mcp.alloc-context.com/mcp` —
> see [USE.md](USE.md).

| | |
|--|--|
| MCP URL | `https://mcp.alloc-context.com/mcp` |
| Transport | Streamable HTTP (`POST /mcp`, JSON-RPC) |
| Discovery | `GET /llms.txt`, `GET /.well-known/x402.json` |
| Bazaar | [CDP discovery MCP](https://docs.cdp.coinbase.com/x402/bazaar) |

Pricing: **$0.02** for cached context and math tools; **$0.05** for
`freshness=live` or `get_portfolio_state`. See [mcp.md](mcp.md).

## Cursor: Bazaar discovery + local stdio

For unpaid local tools, keep stdio AllocContext. Add the CDP discovery MCP to
search Bazaar and call paid tools when needed:

```json
{
  "mcpServers": {
    "x402-discovery": {
      "url": "https://api.cdp.coinbase.com/platform/v2/x402/discovery/mcp"
    },
    "alloc-context": {
      "command": "${workspaceFolder}/.venv/bin/alloc-context",
      "args": ["mcp"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

Example agent flow:

1. Use `search_resources` on the discovery MCP with a query like
   `BTC ETH allocation drift` or `rebalance context`.
2. Confirm AllocContext (`mcp.alloc-context.com`) appears in results.
3. Call `get_context_bundle` via an x402 HTTP client against the hosted URL
   (see below), or use discovery `proxy_tool_call` if your client supports it.

More discovery setup: [mcp-discovery.md](mcp-discovery.md).

## x402 HTTP client (programmatic)

Install hosted extras and use the x402 Python client with a funded Base wallet:

```bash
pip install -e ".[hosted]"
export EVM_PRIVATE_KEY=0x...   # payer wallet ≠ seller X402_PAY_TO
.venv/bin/python scripts/x402-paid-smoke-test.py
```

The smoke script calls `get_market_context` by default. Override the tool:

```bash
MCP_SMOKE_TOOL=get_context_bundle .venv/bin/python scripts/x402-paid-smoke-test.py
```

For custom agents, use the [Coinbase x402 seller quickstart](https://docs.cdp.coinbase.com/x402/quickstart-for-sellers)
and [`@x402/mcp`](https://docs.cdp.coinbase.com/x402/bazaar) client patterns:
wrap an MCP client with automatic payment on 402 responses.

Minimal call shape:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "get_context_bundle",
    "arguments": {
      "scope": "daily",
      "freshness": "cached",
      "assets": ["BTC", "ETH"]
    }
  }
}
```

Unpaid `POST /mcp` returns **402** with `PAYMENT-REQUIRED`; retry with
`PAYMENT-SIGNATURE` per the x402 spec after signing.

## Evaluate before paying

- [examples.md](examples.md) — redacted JSON for context bundle, rebalance
  plan, and band check
- [llms.txt](https://mcp.alloc-context.com/llms.txt) — tool list and keywords
- [context-bundle.md](context-bundle.md) — full schema reference

## Self-host instead

To run your own cache and optional x402 gate: [mcp-http.md](mcp-http.md),
[self-hosting.md](self-hosting.md). Local unpaid stack: [local-dev.md](local-dev.md).
