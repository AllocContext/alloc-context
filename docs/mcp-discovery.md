# MCP discovery (self-hosted HTTP + x402)

Optional metadata for **your** AllocContext HTTP deployment when you enable
x402 ([mcp-http.md](mcp-http.md)). AllocContext does **not** operate a public
hosted endpoint — set `X402_PUBLIC_URL` to **your** HTTPS origin.

For PyPI and the official MCP Registry (stdio self-host listing), see
[distribution.md](distribution.md).

## Public URL

Required for catalog `resource` URLs and static discovery files:

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
| `GET /.well-known/mcp/server-card.json` | Static server card (tool list without paying) |

Paid MCP remains `POST /mcp` behind x402 when `--x402` is enabled.

## Bazaar metadata

When x402 is enabled, `POST /mcp` declares:

- Listing copy tuned for semantic search (holdings, portfolio context, ETF flows)
- Per-tool MCP Bazaar extensions on `tools/call` (indexed separately on settle)
- Fallback aggregate JSON-RPC schema for other MCP methods
- `service_name` and tags on payment resource metadata (CDP index)

Indexing happens after the **first successful settlement** through your
facilitator. Verify alone does not list the service.

### Self-host checklist

1. Deploy HTTP MCP with `[hosted]` and x402 env vars ([mcp-http.md](mcp-http.md)).
2. Set `X402_PUBLIC_URL` to your HTTPS origin.
3. `curl -i -X POST "$X402_PUBLIC_URL/mcp"` → expect **402**.
4. Complete one paid call with an x402 client (any enabled Base stable).
5. Search [CDP Bazaar](https://docs.cdp.coinbase.com/x402/bazaar) or use the
   CDP discovery MCP after settlement.

Run `scripts/x402-production-check.py` on the host after deploy.

**After discovery copy changes:** refresh the CDP index with one paid call per
tool:

```bash
export EVM_PRIVATE_KEY=0x...   # buyer wallet (must differ from X402_PAY_TO)
export MCP_URL=https://mcp.yourdomain.com/mcp
.venv/bin/python scripts/x402-reindex-burst.py
```

### Manual smoke test

```bash
pip install -e ".[hosted]"
export EVM_PRIVATE_KEY=0x...   # buyer wallet
export MCP_URL=https://mcp.yourdomain.com/mcp
.venv/bin/python scripts/x402-paid-smoke-test.py
```

Optional: `MCP_SMOKE_TOOL` (default `get_market_context`).

## Listing title

> AllocContext — portfolio-aware crypto context for agents (MCP + x402)

Privacy and license copy also appear in `GET /llms.txt` (`## Privacy`,
`## License`) and in the Bazaar listing description. Production checks validate
those markers via `scripts/x402-production-check.py`.

Example tool JSON: [examples.md](examples.md).
