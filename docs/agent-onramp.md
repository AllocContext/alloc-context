# Agent on-ramp (~2 minutes)

Give your Cursor or Claude agent **portfolio-aware crypto context** — holdings,
holdings-scoped market, sentiment, macro, and regime — without ad-hoc scraping.

> **Privacy:** nothing stored · one-time read-only · pass-through only — your
> keys, wallet address, and portfolio never persist on our servers. See [USE.md](USE.md).

> **Not financial advice.** Deterministic JSON facts only; no trade execution.

Deep docs: [cursor-mcp.md](cursor-mcp.md) · [agent-integration.md](agent-integration.md)
· [examples.md](examples.md) · [mcp.md](mcp.md)

---

## Track A — stdio bridge (default, local)

Fastest path: local MCP stdio server; portfolio reads use read-only CEX keys in
user config (optional, e.g. Coinbase, Kraken) or hosted `get_portfolio_state`
with `exchange=wallet` and a public EVM address; market context uses the hosted
upstream (x402 payer required for bridge mode).

### 1. Install

```bash
pipx install "alloc-context[mcp,hosted]"
# or: uv tool install "alloc-context[mcp,hosted]"
# from source: pip install -e ".[mcp,hosted]"
```

### 2. Configure

```bash
mkdir -p ~/.config/alloc-context
cp /path/to/alloc-context/config/user.example.yaml ~/.config/alloc-context/user.yaml
```

Edit `user.yaml`:

- **Portfolio (optional):** read-only CEX keys under `exchanges:` (bridge), or
  call hosted `get_portfolio_state` with `exchange=wallet` + `wallet_address`.
- **Hosted market context (required for bridge):** x402 payer — set
  `EVM_PRIVATE_KEY` in your environment or use `payer_private_key_file` in
  `x402:` (see [user-config.md](user-config.md)).

Market tools work without portfolio credentials; bridge portfolio tools need CEX
keys in user config when you use that path.

### 3. Wire into your agent

Cursor or Claude Desktop `mcp.json`:

```json
{
  "mcpServers": {
    "alloc-context": {
      "command": "alloc-context",
      "args": [
        "mcp",
        "--user-config",
        "/Users/you/.config/alloc-context/user.yaml"
      ]
    }
  }
}
```

Use an **absolute** path for `--user-config`. Example:
[cursor-mcp-bridge.example.json](cursor-mcp-bridge.example.json).

### 4. First call

Example agent prompt:

> What's in my portfolio and how does market context look for what I hold?
> Optional: check drift vs a 60/30/10 BTC/ETH/cash target.

Call `get_context_bundle` (add `target_pct` in tool args for allocation
analysis). With CEX keys configured in the bridge, omitting `assets` auto-scopes
market data to your holdings.

### 5. What you get

A [ContextBundle](context-bundle.md): `portfolio` (holdings, NAV, weights),
`sentiment`, `macro`, `regime`, optional `delta`, and optional
`allocation_analysis` when you pass targets. Redacted sample:

```json
{
  "as_of": "2026-05-28T12:00:00+00:00",
  "freshness": "cached",
  "portfolio": {
    "available": true,
    "nav_usd": 125000.0,
    "holdings": [
      {"symbol": "BTC", "weight_pct": 0.67, "kind": "band"},
      {"symbol": "ETH", "weight_pct": 0.287, "kind": "band"}
    ]
  },
  "sentiment": {"available": true, "fear_greed": {"value": 52, "classification": "Neutral"}},
  "macro": {"available": true}
}
```

Full examples: [examples.md](examples.md).

---

## Track B — hosted x402 (no local install)

For agents that call a public endpoint directly — pay per call on Base (USDC
or EURC).

| | |
|--|--|
| MCP URL | `https://mcp.alloc-context.com/mcp` |
| Discovery | `GET /llms.txt`, `GET /.well-known/x402.json` |
| Pricing | **$0.02** cached context/math · **$0.05** live ingest or portfolio |

### 1. Payer wallet

Fund a Base mainnet wallet and export the private key:

```bash
export EVM_PRIVATE_KEY=0x...   # payer wallet, not the seller address
```

### 2. First paid call

```bash
git clone https://github.com/AllocContext/alloc-context.git
cd alloc-context
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[hosted]"
.venv/bin/python scripts/x402-paid-smoke-test.py
```

Default smoke calls `get_market_context`. Override:

```bash
.venv/bin/python scripts/x402-paid-smoke-test.py --tool get_context_bundle
```

Programmatic clients: [agent-integration.md](agent-integration.md).
LangChain tools: [langchain-integration.md](langchain-integration.md).

---

## Which track?

| | Track A (bridge) | Track B (hosted) |
|--|------------------|------------------|
| Install | `pipx` / local venv | None (HTTP + x402) |
| Portfolio source | CEX keys in user.yaml (bridge) | CEX keys or wallet address per call |
| Cost | x402 for market context | Per-call x402 |
| Best for | Cursor / Claude daily use | Agents, wallets, serverless |

Self-host evaluation (ingest + MCP on your infra): [self-hosting.md](self-hosting.md).
**Docker Compose (local eval):** `./docker/up.sh` or [docker-self-host.md](docker-self-host.md).

---

## Next steps

- All tools and args: [mcp.md](mcp.md)
- ContextBundle fields: [context-bundle.md](context-bundle.md)
- CDP Bazaar discovery: [mcp-discovery.md](mcp-discovery.md)
- LangChain / agent frameworks: [langchain-integration.md](langchain-integration.md)
- Architecture pattern: [deterministic-context-mcp-pattern.md](deterministic-context-mcp-pattern.md)
- Embed or license inquiries: GitHub Issues (inbound only; no outbound sales)
