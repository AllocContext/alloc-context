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

## Portfolio response

When exchange keys are configured, portfolio tools return `holdings[]` with
every recognized balance (qty, USD mark, weight). Assets like HYPE are included
when a USD price is available; unpriced symbols appear in `holdings[]` with
null marks and in `unrecognized[]`.

Allocation drift and rebalance hints are **opt-in** via `target_allocation` in
user config or `target_pct` on the tool call. When enabled, results appear in
`allocation_analysis`, not mixed into default portfolio fields.

## Missing configuration

Tools return `available: false` with a `setup` block explaining how to enable
portfolio, x402 payment, or allocation analysis.

## Related

- [USE.md](USE.md) — license and allowed uses
- [cursor-mcp.md](cursor-mcp.md) — stdio setup
- [agent-integration.md](agent-integration.md) — hosted URL
