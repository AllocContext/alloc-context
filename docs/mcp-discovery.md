# MCP discovery (Bazaar + agent search)

Paid AllocContext endpoints expose Bazaar metadata so CDP and other
facilitators can index the service after the first successful settlement.

## Public URL

Set the HTTPS origin agents will call (required for catalog `resource` URLs):

```bash
export X402_PUBLIC_URL=https://mcp.yourdomain.com
```

Also accepted: `ALLOC_CONTEXT_MCP_PUBLIC_URL`.

Without this, static discovery files return 404 and the 402 `resource` field
may show localhost.

## Discovery endpoints (free)

| Path | Purpose |
|------|---------|
| `GET /health` | Liveness |
| `GET /llms.txt` | Agent-readable service summary |
| `GET /.well-known/x402.json` | Machine-readable tool manifest |

Paid MCP remains `POST /mcp` behind x402 when `--x402` is enabled.

## Bazaar metadata

When x402 is enabled, `POST /mcp` declares:

- Listing copy tuned for semantic search (BTC/ETH allocation, rebalance, drift)
- Bazaar extension with streamable HTTP JSON-RPC example and tool name enum
- Per-tool MCP schemas (see `alloccontext/mcp/bazaar.py`)

Indexing happens after the **first successful settlement** through your
facilitator. Verify alone does not list the service.

### Production checklist

1. Deploy HTTP MCP with `[hosted]` and x402 env vars ([mcp-http.md](mcp-http.md)).
2. Set `X402_PUBLIC_URL` to your HTTPS origin.
3. `curl -i -X POST "$X402_PUBLIC_URL/mcp"` → expect **402**.
4. Complete one paid call with an x402 client (any enabled Base stable).
5. Search CDP Bazaar or use the discovery MCP (below).

Run `scripts/x402-production-check.py` on the host after deploy.

## Weekly paid smoke (Bazaar activity)

CDP Bazaar drops resources with **no paid calls in 30 days**. Keep the hosted
listing warm with a cheap weekly settlement (~$0.02 for cached
`get_market_context` on Base mainnet).

### Buyer wallet

Use a **dedicated tester wallet** — not the seller `X402_PAY_TO` address.
CDP rejects payments when payer and payTo match (`self_send_not_allowed`).

1. Create or reuse an EVM wallet for CI only.
2. Fund it with a small balance of **Base mainnet USDC** (Circle on Base).
   A few dollars lasts months at one call per week.
3. Add the wallet private key as GitHub repository secret **`EVM_PRIVATE_KEY`**
   on `negillett/alloc-context` (Settings → Secrets and variables → Actions).

Testnet USDC does **not** count toward Bazaar visibility — production uses
`eip155:8453` and the CDP facilitator.

### Manual run

```bash
pip install -e ".[hosted]"
export EVM_PRIVATE_KEY=0x...   # buyer wallet; must differ from X402_PAY_TO
python scripts/x402-paid-smoke-test.py
```

Optional: `MCP_URL` (default `https://mcp.alloc-context.com/mcp`),
`MCP_SMOKE_TOOL` (default `get_market_context`).

### Scheduled CI

Workflow [`.github/workflows/paid-smoke.yml`](../.github/workflows/paid-smoke.yml)
runs **Wednesdays 06:45 UTC** and supports `workflow_dispatch`. After adding
`EVM_PRIVATE_KEY`, trigger once manually to confirm settlement before relying
on the schedule.

## Discovery MCP in Cursor

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

1. Search Bazaar for BTC/ETH allocation or rebalance context.
2. Confirm AllocContext appears after your first paid settlement.
3. Call paid tools via an x402 HTTP client against `X402_PUBLIC_URL/mcp`.

For unpaid local use, keep stdio `alloc-context mcp`.

## Listing title

> AllocContext — BTC/ETH allocation drift, rebalance moves & market context

Tags: `btc`, `eth`, `rebalance`, `allocation`, `crypto`
