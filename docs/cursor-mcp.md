# Cursor MCP setup

Use AllocContext in Cursor over stdio. The **default path** is **self-host**
(local SQLite + ingest, or live portfolio reads only).

> **Privacy:** pass-through for live reads; local ingest data stays on your
> machine. See [USE.md](USE.md) and [user-config.md](user-config.md).

The former hosted bridge (`mcp.alloc-context.com`) is **retired**. Legacy bridge
docs: [cursor-mcp-bridge.example.json](cursor-mcp-bridge.example.json),
[agent-integration.md](agent-integration.md).

## Install

```bash
pip install -e ".[mcp]"
# From PyPI: pip install "alloc-context[mcp]"
```

## Default: self-host (recommended)

**1.** Copy [config/config.example.yaml](../config/config.example.yaml) →
`config/config.yaml` and [config/user.example.yaml](../config/user.example.yaml) →
`~/.config/alloc-context/user.yaml`.

**2.** Enable self-host in `user.yaml`:

```yaml
self_host: true
config: /absolute/path/to/alloc-context/config/config.yaml
```

**3.** Add keys to `.env` (from `.env.example`) when you want exchange portfolio
or richer macro feeds.

**4.** Populate SQLite (optional but recommended for macro/regime):

```bash
python -m alloccontext --config config/config.yaml ingest
```

**5.** Cursor `mcp.json`:

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

Use an absolute path for `--user-config`. See [cursor-mcp.example.json](cursor-mcp.example.json).

Alternative: set `ALLOC_CONTEXT_CONFIG` and omit bridge user config — see
[self-hosting.md](self-hosting.md).

## Legacy: bridge + hosted upstream (retired)

The bridge path called a paid hosted upstream for market context. That endpoint
is no longer operated. Do not configure `upstream:` in `user.yaml` unless you
point at infrastructure you control.

## Tools

| Tool | Keys required |
|------|----------------|
| `get_context_bundle` | Self-host: local DB and/or CEX keys in config |
| `get_market_context` | Self-host: local DB |
| `get_portfolio_state` | CEX keys in config or `wallet_address` in tool args |
| `get_rebalance_plan` | None (pure math) |
| `check_allocation_band` | None (pure math) |

Missing config returns `available: false` with a `setup` block.

All successful responses include `as_of` and `age_seconds`.
