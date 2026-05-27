# MCP HTTP + x402

Streamable HTTP transport for paid/hosted MCP. Stdio remains available for
local Cursor use.

## Install

```bash
pip install -e ".[hosted]"
```

## Local HTTP (no payment)

```bash
alloc-context mcp --transport http --host 127.0.0.1 --port 8000
```

Health: `GET /health`  
MCP endpoint: `POST /mcp` (streamable HTTP)

## x402 (testnet default)

Set seller wallet and enable payment gate:

```bash
export X402_PAY_TO=0xYourWallet
export X402_FACILITATOR_URL=https://x402.org/facilitator
export X402_NETWORK=eip155:84532
export X402_PRICE_MCP=$0.02

alloc-context mcp --transport http --x402
```

Unpaid `POST /mcp` returns **402 Payment Required** with USDC payment metadata.
After payment, retry with `PAYMENT-SIGNATURE` header per x402 spec.

## Production (CDP facilitator)

```bash
export X402_FACILITATOR_URL=https://api.cdp.coinbase.com/platform/v2/x402
export X402_NETWORK=eip155:8453
export CDP_API_KEY_ID=...
export CDP_API_KEY_SECRET=...
export X402_PUBLIC_URL=https://mcp.yourdomain.com
export X402_PAY_TO=0xYourWallet
```

CDP auth is required for verify/settle when using the CDP facilitator URL.
The hosted install includes `cdp-sdk`, which wires `CDP_API_KEY_*` into the
facilitator client automatically.

After deploy, run:

```bash
source /opt/trading/shared/.env
python scripts/x402-production-check.py
```

Then complete one paid tool call with an x402 HTTP client (mainnet USDC on Base)
and confirm settlement to `X402_PAY_TO`.

See [Coinbase x402 seller quickstart](https://docs.cdp.coinbase.com/x402/quickstart-for-sellers).

Discovery: [mcp-discovery.md](mcp-discovery.md) — Bazaar metadata, `llms.txt`,
and `/.well-known/x402.json`.

Verification scripts: `scripts/x402-production-check.py`,
`scripts/x402-paid-smoke-test.py` (buyer wallet required; payer must differ
from `X402_PAY_TO`).

## Staleness: `freshness` on `get_market_context`

| Value | Behavior |
|-------|----------|
| `cached` (default) | Read from SQLite ingest DB |
| `live` | Run full ingest, then rollup (needs operator API keys on host) |

## Entry points

| Command | Use |
|---------|-----|
| `alloc-context mcp` | stdio (Cursor) |
| `alloc-context mcp --transport http` | local HTTP |
| `alloc-context mcp --transport http --x402` | paid HTTP |
| `alloc-context-mcp-http` | HTTP from env (`ALLOC_CONTEXT_MCP_*`, `X402_*`) |
