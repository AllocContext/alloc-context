# Cursor MCP setup

Use AllocContext in Cursor over stdio. The **default path** is the local
**bridge** (portfolio local + hosted market context). Self-host ingest remains
available for power users.

> **Privacy:** nothing stored · one-time read-only · pass-through only. See
> [USE.md](USE.md) and [user-config.md](user-config.md).

For the **hosted paid endpoint** (x402 on `mcp.alloc-context.com`) without a
local bridge, see [agent-integration.md](agent-integration.md).

## Install

```bash
pip install -e ".[mcp]"
# Bridge → hosted upstream (Path A):
pip install -e ".[hosted]"
```

## Default: bridge + user config (Path A)

Copy [config/user.example.yaml](../config/user.example.yaml) to
`~/.config/alloc-context/user.yaml` and add exchange keys (optional) and x402
payer config. See [user-config.md](user-config.md).

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

Portfolio requires exchange credentials in user config. Market context calls
the hosted upstream (x402 payer required). When both are configured, omitting
`assets` on `get_market_context` / `get_context_bundle` auto-scopes market
data to your holdings (symbols only upstream). See [user-config.md](user-config.md).

Examples: [cursor-mcp-bridge.example.json](cursor-mcp-bridge.example.json).
The repo [`.cursor/mcp.json`](../.cursor/mcp.json) uses the same bridge pattern.

## Self-host ingest (Path C)

Requires a local SQLite DB populated by ingest (`python -m alloccontext ingest`).
Use [cursor-mcp.example.json](cursor-mcp.example.json) or merge:

```json
{
  "mcpServers": {
    "alloc-context": {
      "command": "alloc-context",
      "args": ["mcp"],
      "env": {
        "ALLOC_CONTEXT_CONFIG": "/path/to/config/config.yaml"
      }
    }
  }
}
```

Or set `self_host: true` and `config:` in `user.yaml` instead of `--user-config`
bridge mode. See [self-hosting.md](self-hosting.md).

Alternative entry point: `alloc-context-mcp` (same stdio server).

## Tools

| Tool | Keys required |
|------|----------------|
| `get_context_bundle` | Bridge: x402 payer; portfolio: exchange keys in user.yaml. Self-host: local DB. |
| `get_market_context` | Bridge: x402 payer. Self-host: local DB. |
| `get_portfolio_state` | Bridge: exchange keys in user.yaml (or tool args). |
| `get_rebalance_plan` | None (pure math) |
| `check_allocation_band` | None (pure math) |

Missing config returns `available: false` with a `setup` block.

All successful responses include `as_of` and `age_seconds`.
