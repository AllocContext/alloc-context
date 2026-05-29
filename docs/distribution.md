# Distribution and discoverability

How AllocContext appears outside the CDP Bazaar: GitHub metadata, the official
MCP Registry, PyPI, and curated agent directories.

**Production MCP:** `https://mcp.alloc-context.com/mcp`  
**Discovery:** [llms.txt](https://mcp.alloc-context.com/llms.txt),
[x402 manifest](https://mcp.alloc-context.com/.well-known/x402.json)

## Short blurb (copy-paste)

Use this for directory forms, community posts, and registry descriptions:

```text
AllocContext — deterministic BTC/ETH allocation context for AI agents over MCP.
Drift and band checks, USD rebalance plans, fused market backdrop (Fear & Greed,
Kalshi, macro, ETF flows), optional live Kraken/Coinbase reads. Hosted on Base
with x402 pay-per-call ($0.02 cached / $0.05 live). https://mcp.alloc-context.com/mcp
```

## GitHub repository metadata

| Field | Value |
|-------|-------|
| **Description** | BTC/ETH allocation MCP for agents — drift, rebalance, market context. Hosted: https://mcp.alloc-context.com/mcp (x402 on Base). |
| **Topics** | `mcp`, `x402`, `bitcoin`, `ethereum`, `model-context-protocol`, `agents`, `portfolio` |
| **Website** | `https://mcp.alloc-context.com/llms.txt` |

Update from a machine with repo admin access:

```bash
gh repo edit negillett/alloc-context \
  --description "BTC/ETH allocation MCP for agents — drift, rebalance, market context. Hosted: https://mcp.alloc-context.com/mcp (x402 on Base)." \
  --add-topic mcp --add-topic x402 --add-topic bitcoin --add-topic ethereum \
  --add-topic model-context-protocol --add-topic agents --add-topic portfolio \
  --homepage "https://mcp.alloc-context.com/llms.txt"
```

(AllocContext workspace: prefix with `scripts/with-alloc-gh.sh` if using the
parent-folder PAT.)

## Official MCP Registry

The canonical directory is [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io).
PulseMCP, Smithery, and other lists ingest from it.

This repo ships [`server.json`](../server.json) at the root with:

- **Remote:** `streamable-http` → `https://mcp.alloc-context.com/mcp`
- **Package:** PyPI `alloc-context` (stdio via `alloc-context mcp`) — publish to
  PyPI first; see [publishing.md](publishing.md).

### Publish steps

1. Install the publisher CLI (see [MCP publishing guide](https://modelcontextprotocol.io/registry/publishing)).
2. From the repo root, authenticate as `negillett` (GitHub OAuth or OIDC in CI).
3. Run the **release** workflow or bump via `scripts/bump_version.py` — see
   [publishing.md](publishing.md).
4. Run `mcp-publisher publish` (or the current equivalent from the registry docs).

Verify after publish:

```bash
curl -sS "https://registry.modelcontextprotocol.io/v0/servers?search=negillett/alloc-context" | jq .
```

Namespace `io.github.negillett/alloc-context` requires GitHub auth as the repo owner.

## PyPI

Package name: **`alloc-context`**. Metadata lives in `pyproject.toml`; release
process in [publishing.md](publishing.md).

After the first PyPI release, README and project URLs surface the hosted MCP
endpoint automatically via `[project.urls]`.

## Other directories

| Directory | How to submit | Notes |
|-----------|---------------|-------|
| **MCP Registry** | `server.json` + `mcp-publisher` | Primary; do this first |
| **PulseMCP** | Email `hello@pulsemcp.com` with blurb + GitHub URL | Often picks up registry entries; email if missing after ~1 week |
| **Smithery** | [smithery.ai](https://smithery.ai) submit flow | Prefer registry publish; HTTP/x402 remote URL |
| **Glama** | [glama.ai](https://glama.ai) MCP directory | Remote URL + tags |
| **awesome-mcp** | PR to a maintained awesome list | Link `docs/agent-integration.md` |

Document stable inbound links in the workspace discoverability roadmap when live.

## Coinbase / x402 ecosystem

Optional one-time post (developer community or x402 thread):

- Link hosted MCP + [agent-integration.md](agent-integration.md)
- Mention CDP Bazaar discovery and weekly mainnet activity for listing warmth
- Do not share secrets, wallet keys, or internal VPS details

## Related docs

| Doc | Purpose |
|-----|---------|
| [mcp-discovery.md](mcp-discovery.md) | CDP Bazaar and x402 manifest |
| [agent-integration.md](agent-integration.md) | Paid HTTP MCP for agents |
| [publishing.md](publishing.md) | PyPI + VPS release workflow |
