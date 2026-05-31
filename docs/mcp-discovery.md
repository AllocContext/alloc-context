# MCP discovery (Bazaar + agent search)

Paid AllocContext endpoints expose Bazaar metadata so CDP and other
facilitators can index the service after the first successful settlement.

For GitHub topics, PyPI, and the official MCP Registry, see
[distribution.md](distribution.md).

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

- Listing copy tuned for semantic search (holdings, portfolio context, ETF flows)
- Per-tool MCP Bazaar extensions on `tools/call` (indexed separately on settle)
- Fallback aggregate JSON-RPC schema for other MCP methods
- `service_name` and tags on payment resource metadata (CDP index)

Indexing happens after the **first successful settlement** through your
facilitator. Verify alone does not list the service.

### Production checklist

1. Deploy HTTP MCP with `[hosted]` and x402 env vars ([mcp-http.md](mcp-http.md)).
2. Set `X402_PUBLIC_URL` to your HTTPS origin.
3. `curl -i -X POST "$X402_PUBLIC_URL/mcp"` → expect **402**.
4. Complete one paid call with an x402 client (any enabled Base stable).
5. Search CDP Bazaar or use the discovery MCP (below).

Run `scripts/x402-production-check.py` on the host after deploy.

**After discovery copy changes:** refresh the CDP index with one paid call per
tool (~$0.16 for cached math/context tools):

```bash
export EVM_PRIVATE_KEY=0x...   # buyer wallet
.venv/bin/python scripts/x402-reindex-burst.py
```

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
.venv/bin/python scripts/x402-paid-smoke-test.py
```

Or from repo root with a venv: `python scripts/x402-reindex-burst.py` (uses
`.venv/bin/python` when present).

Optional: `MCP_URL` (default `https://mcp.alloc-context.com/mcp`),
`MCP_SMOKE_TOOL` (default `get_market_context`).

Logs redact `0x` wallet and contract addresses by default. Set
`SMOKE_LOG_ADDRESSES=1` for full addresses when debugging locally.

### Scheduled CI

Workflow [`.github/workflows/paid-smoke.yml`](../.github/workflows/paid-smoke.yml)
runs **Wednesdays 06:45 UTC** and supports `workflow_dispatch`. After adding
`EVM_PRIVATE_KEY`, trigger once manually to confirm settlement before relying
on the schedule.

## Discovery MCP in Cursor

Add the CDP discovery MCP alongside the AllocContext bridge — see
[cursor-mcp.md](cursor-mcp.md) for `mcp.json` (default `--user-config`).

```json
{
  "mcpServers": {
    "x402-discovery": {
      "url": "https://api.cdp.coinbase.com/platform/v2/x402/discovery/mcp"
    }
  }
}
```

1. Search Bazaar for portfolio holdings or crypto market context.
2. Confirm AllocContext appears after your first paid settlement.
3. Call paid tools via an x402 HTTP client against `X402_PUBLIC_URL/mcp`.

For local bridge or self-host stdio, see [cursor-mcp.md](cursor-mcp.md).

Paid HTTP integration (x402 client, Bazaar search flow):
[agent-integration.md](agent-integration.md). Example tool JSON:
[examples.md](examples.md).

## Listing title

> AllocContext — portfolio-aware crypto context for agents (MCP + x402)

Privacy and license copy also appear in `GET /llms.txt` (`## Privacy`,
`## License`) and in the Bazaar listing description. Production checks validate
those markers via `x402_production_check.py`.

Tags: `btc`, `eth`, `portfolio`, `holdings`, `mcp` (plus additional tags in
`/.well-known/x402.json`)
