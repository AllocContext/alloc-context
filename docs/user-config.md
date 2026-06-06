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
| **Bridge (default)** | CEX keys + x402 payer | Portfolio local (CEX); context via hosted upstream |
| **Self-host** | `self_host: true` + `config:` | Full local ingest + MCP (no upstream paywall) |
| **Legacy** | omit `--user-config`; no default file | Local server `config.yaml` only |

## Portfolio response

When CEX keys are configured in user config, bridge portfolio tools return
`holdings[]` with
every recognized balance (qty, USD mark, weight). Assets like HYPE are included
when a USD price is available; unpriced symbols appear in `holdings[]` with
null marks and in `unrecognized[]`.

Allocation drift and rebalance hints are **opt-in** via `target_allocation` in
user config or `target_pct` on the tool call. When enabled, results appear in
`allocation_analysis`, not mixed into default portfolio fields.

## Bridge market auto-scoping (Path A)

When CEX keys and an x402 payer are configured, omitting `assets` on
`get_market_context` or `get_context_bundle` derives upstream symbol scope from
local holdings (excluding stables/cash). Only **symbol strings** are sent to the
hosted server — never quantities, NAV, or credentials.

Responses include `assets_scope`:

| Value | Meaning |
|-------|---------|
| `portfolio` | Symbols derived from live holdings |
| `explicit` | You passed `assets` on the tool call |
| `default` | Hosted default (`BTC`/`ETH`) — no CEX keys or empty holdings |
| `portfolio_unavailable` | Exchange fetch failed; fell back to hosted default |

If portfolio fetch fails, market context may not include your alts even though
holdings appear in `get_portfolio_state`. Configure x402 before exchange fetch
runs on bundle calls (no exchange hit when payer is missing).

`get_context_at` and `get_context_delta` do **not** auto-scope — pass `assets`
when you need alt filters on historical reads.

## Missing configuration

Tools return `available: false` with a `setup` block explaining how to enable
portfolio, x402 payment, or allocation analysis.

## Local theses (expectation review)

Optional `theses:` entries in `user.yaml` (or per-call `theses` on
`get_context_bundle`) enable deterministic `expectation_review` scoring. Core
never stores beliefs — pass-through only. Each thesis requires `id`,
`recorded_at`, and `claims[]`. See
[context-bundle.md](context-bundle.md) and `config/user.example.yaml`.

`ALLOCATION_FIT` claims need `target_allocation` / `band` (here or on the tool
call). Bridge mode loads baselines via hosted `get_context_at` per `recorded_at`.

## Hosted wallet portfolio (no user.yaml)

On the hosted MCP, call `get_portfolio_state` with `exchange=wallet` and a
public EVM `wallet_address` (keyless for the caller). The server uses its own
on-chain provider credentials — not your keys. See [mcp.md](mcp.md).

## Related

- [USE.md](USE.md) — license and allowed uses
- [cursor-mcp.md](cursor-mcp.md) — stdio setup
- [agent-integration.md](agent-integration.md) — hosted URL
