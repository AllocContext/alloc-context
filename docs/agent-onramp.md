# Agent on-ramp (~2 minutes)

Give your Cursor or Claude agent **portfolio-aware crypto context** — holdings,
holdings-scoped market, sentiment, macro, and regime — without ad-hoc scraping.

> **Privacy:** pass-through for live reads; local ingest data stays on your
> machine. See [USE.md](USE.md).

> **Not financial advice.** Deterministic JSON facts only; no trade execution.

**Self-host via PyPI** — stdio MCP + optional local ingest. The hosted MCP at
`mcp.alloc-context.com` is **retired**.

Deep docs: [cursor-mcp.md](cursor-mcp.md) · [self-hosting.md](self-hosting.md)
· [examples.md](examples.md) · [mcp.md](mcp.md)

---

## 1. Install

```bash
pip install "alloc-context[mcp]"
# or: pipx install "alloc-context[mcp]"
# from source: pip install -e ".[mcp]"
```

## 2. Configure

In your checkout (or install dir):

```bash
cp config/config.example.yaml config/config.yaml
cp .env.example .env
```

Edit `config/config.yaml` and `.env`:

- **Portfolio (optional):** read-only CEX keys for ingest and live reads.
- **Wallet (optional):** `get_portfolio_state` with `exchange=wallet` and a
  public EVM address — no private key.

See [self-hosting.md](self-hosting.md) for optional feed keys (FRED, etc.).

## 3. Populate cache

```bash
source .env
python -m alloccontext --config config/config.yaml ingest
```

Run before a session or when you need fresh facts. Cached MCP responses work
from SQLite without re-ingesting if data is already present.

## 4. Wire into your agent

Cursor or Claude Desktop `mcp.json` — use **absolute** paths:

```json
{
  "mcpServers": {
    "alloc-context": {
      "command": "alloc-context",
      "args": [
        "mcp",
        "--config",
        "/absolute/path/to/alloc-context/config/config.yaml"
      ],
      "env": {
        "ALLOC_CONTEXT_DB": "/absolute/path/to/alloc-context/state/alloccontext.db"
      }
    }
  }
}
```

Example: [cursor-mcp.example.json](cursor-mcp.example.json). Reload Cursor after
edits.

**`user.yaml` not required.** Legacy bridge mode used
`~/.config/alloc-context/user.yaml` — remove or rename that file when using
`--config`. Details: [cursor-mcp.md](cursor-mcp.md).

## 5. First call

Example agent prompt:

> What's in my portfolio and how does market context look for what I hold?
> Optional: check drift vs a 60/30/10 BTC/ETH/cash target.

Call `get_context_bundle`. Pass `target_pct` for allocation analysis. Pass
`assets` explicitly when you want alts in market context (default filter is
BTC and ETH when omitted).

## 6. What you get

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

## Alternatives

| Path | When |
|------|------|
| [Docker Compose](docker-self-host.md) | Containerized local eval (HTTP on loopback) |
| `./scripts/local-up.sh` | Native loopback HTTP `:8001` for non-stdio clients — [self-hosting.md](self-hosting.md) |

---

## Next steps

- All tools and args: [mcp.md](mcp.md)
- ContextBundle fields: [context-bundle.md](context-bundle.md)
- PyPI + MCP Registry: [distribution.md](distribution.md)
- Other agent frameworks: [cursor-mcp.md](cursor-mcp.md)
- Architecture pattern: [deterministic-context-mcp-pattern.md](deterministic-context-mcp-pattern.md)
- Embed or license inquiries: GitHub Issues (inbound only; no outbound sales)
