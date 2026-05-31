# User config (`user.yaml`)

Privacy: **nothing stored · one-time read-only · pass-through only.** See
[USE.md](USE.md).

The bridge reads `~/.config/alloc-context/user.yaml` (or `--user-config` /
`ALLOC_CONTEXT_USER_CONFIG`). Copy [config/user.example.yaml](../config/user.example.yaml)
as a starting point.

## Cursor `mcp.json` (default path)

```json
{
  "mcpServers": {
    "alloc-context": {
      "command": "alloc-context",
      "args": ["mcp", "--user-config", "~/.config/alloc-context/user.yaml"]
    }
  }
}
```

## Modes

| Mode | user.yaml | Behavior |
|------|-----------|----------|
| **Bridge (default)** | exchange keys + x402 payer | Portfolio local; context via hosted upstream |
| **Self-host** | `self_host: true` + `config:` | Full local ingest + MCP (no upstream paywall) |
| **Legacy** | omit `--user-config`; no default file | Local server `config.yaml` only |

## Missing configuration

Tools return `available: false` with a `setup` block explaining how to enable
portfolio, x402 payment, or allocation analysis.

## Related

- [USE.md](USE.md) — license and allowed uses
- [cursor-mcp.md](cursor-mcp.md) — stdio setup
- [agent-integration.md](agent-integration.md) — hosted URL
