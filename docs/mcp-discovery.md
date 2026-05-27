# MCP discovery (Bazaar + agent search)

Phase C adds Bazaar metadata so CDP and other facilitators can index the paid
AllocContext MCP endpoint after the first successful settlement.

## Public URL

Set the HTTPS origin agents will call (required for catalog `resource` URLs):

```bash
export X402_PUBLIC_URL=https://mcp.yourdomain.com
```

Also accepted: `ALLOC_CONTEXT_MCP_PUBLIC_URL`.

Without this, Bazaar indexing still works from request URLs, but static discovery
files return 404 and the 402 `resource` field may show localhost.

## Discovery endpoints (free)

| Path | Purpose |
|------|---------|
| `GET /health` | Liveness |
| `GET /llms.txt` | Agent-readable service summary |
| `GET /.well-known/x402.json` | Machine-readable tool manifest |

Paid MCP remains `POST /mcp` behind x402 when `--x402` is enabled.

## Bazaar metadata

When x402 is enabled, the `POST /mcp` route declares:

- **Listing copy** tuned for semantic search (BTC/ETH allocation, rebalance, drift)
- **Bazaar extension** with streamable HTTP JSON-RPC example and tool name enum
- **Per-tool MCP schemas** (see `alloccontext/mcp/bazaar.py`) for documentation

The resource server registers `bazaar_resource_server_extension` so HTTP method
and path params are enriched on each 402 response.

Indexing happens after the **first successful settlement** through your
facilitator (testnet: `https://x402.org/facilitator`; production: CDP). Verify
alone does not list the service.

### Testnet checklist

1. Deploy HTTP MCP with `[hosted]` extra and x402 env vars (see `docs/mcp-http.md`).
2. Set `X402_PUBLIC_URL` to your HTTPS origin.
3. `curl -i -X POST "$X402_PUBLIC_URL/mcp"` → expect **402**.
4. Pay once with an x402 client (Base Sepolia USDC).
5. Search CDP Bazaar or use discovery MCP (below).

## Dogfood: x402-discovery-mcp in Cursor

Add the CDP discovery MCP alongside local stdio AllocContext:

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

Workflow:

1. Ask the agent to search Bazaar for BTC/ETH allocation or rebalance context.
2. Confirm AllocContext appears (after your first paid call on production/testnet).
3. Call paid tools via an x402-enabled HTTP MCP client against `X402_PUBLIC_URL/mcp`.

For local unpaid dogfooding, keep using stdio `alloc-context mcp`.

## Listing title (Bazaar / Agent.market)

> AllocContext — BTC/ETH allocation drift, rebalance moves & market context

Tags: `btc`, `eth`, `rebalance`, `allocation`, `crypto`
