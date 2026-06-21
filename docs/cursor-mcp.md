# Cursor MCP setup

Use AllocContext in Cursor over stdio. The **default path** is **self-host**
(local SQLite + ingest).

> **Privacy:** pass-through for live reads; local ingest data stays on your
> machine. See [USE.md](USE.md).

The former hosted bridge (`mcp.alloc-context.com`) is **retired**. Legacy bridge
docs: [cursor-mcp-bridge.example.json](cursor-mcp-bridge.example.json),
[agent-integration.md](agent-integration.md), [user-config.md](user-config.md).

## Install

```bash
pip install -e ".[mcp]"
# From PyPI: pip install "alloc-context[mcp]"
```

## Default: self-host (recommended)

**1.** Copy [config/config.example.yaml](../config/config.example.yaml) →
`config/config.yaml`.

**2.** Copy [.env.example](../.env.example) → `.env` and add read-only exchange
keys plus optional feed keys (FRED, etc.).

**3.** Populate SQLite (recommended before first MCP session):

```bash
source .env   # optional if keys are exported elsewhere
python -m alloccontext --config config/config.yaml ingest
```

**4.** Cursor `mcp.json` — point MCP at your config and DB (absolute paths):

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

See [cursor-mcp.example.json](cursor-mcp.example.json). Reload Cursor after edits.

**Optional:** `scripts/local-up.sh` starts loopback HTTP MCP on `:8001` for
orchestrator or other HTTP clients — see [self-hosting.md](self-hosting.md).

## Bridge user config (legacy, optional)

`~/.config/alloc-context/user.yaml` is only needed for the retired **bridge**
mode (local portfolio + paid upstream). Self-host does **not** require it.
If that file exists, MCP auto-discovers it — remove or rename it when using
`--config` directly.

## Tools

| Tool | Keys required |
|------|----------------|
| `get_context_bundle` | Cached: local DB; live: `.env` keys + `freshness=live` |
| `get_market_context` | Cached: local DB |
| `get_portfolio_state` | CEX keys on tool call, or `wallet_address` |
| `get_rebalance_plan` | None (pure math) |
| `check_allocation_band` | None (pure math) |

Missing config returns `available: false` with a `setup` block.

All successful responses include `as_of` and `age_seconds`.

## LangChain and other agent frameworks

AllocContext does not ship a LangChain helper. Use
[langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
to connect an agent to the stdio MCP server configured above (`alloc-context mcp
--config …`).
