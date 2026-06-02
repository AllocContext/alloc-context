# Distribution and discoverability

How AllocContext appears outside the CDP Bazaar: GitHub metadata, the official
MCP Registry, PyPI, and curated agent directories.

**Production MCP:** `https://mcp.alloc-context.com/mcp`  
**Discovery:** [llms.txt](https://mcp.alloc-context.com/llms.txt),
[x402 manifest](https://mcp.alloc-context.com/.well-known/x402.json)

## Short blurb (copy-paste)

Use this for directory forms, community posts, and registry descriptions.

```text
AllocContext — portfolio-aware crypto context for AI agents over MCP. Discover
holdings and holdings-scoped market, sentiment, macro, and regime; optional
allocation analysis. Privacy: nothing stored; one-time read-only; pass-through
only. Source-available (Elastic License 2.0); self-host friendly. Official
hosted MCP: https://mcp.alloc-context.com/mcp — see docs/USE.md. x402 on Base
($0.02 cached / $0.05 live).
```

Architecture pattern (ingest → rollup → MCP → x402):
[docs/deterministic-context-mcp-pattern.md](deterministic-context-mcp-pattern.md).

## GitHub repository metadata

| Field | Value |
|-------|-------|
| **Description** | Portfolio crypto context MCP — holdings-scoped market for agents. Hosted: https://mcp.alloc-context.com/mcp (x402). ELv2. |
| **Topics** | `mcp`, `x402`, `bitcoin`, `ethereum`, `model-context-protocol`, `agents`, `portfolio` |
| **Website** | `https://mcp.alloc-context.com/llms.txt` |

The workspace PAT cannot set these via `gh repo edit` (needs **Administration**
scope). Use the GitHub UI:

1. Open [github.com/AllocContext/alloc-context](https://github.com/AllocContext/alloc-context)
2. **Settings** is not required — click the **gear** next to About on the repo home
3. Set **Description** and **Website** as in the table above
4. Add **Topics** from the table (include `model-context-protocol`)

Or, from a machine with a PAT that has **Administration** on the repo:

```bash
gh repo edit AllocContext/alloc-context \
  --description "Portfolio crypto context MCP for agents — holdings, market, optional drift. Hosted: https://mcp.alloc-context.com/mcp (x402). ELv2." \
  --add-topic mcp --add-topic x402 --add-topic bitcoin --add-topic ethereum \
  --add-topic model-context-protocol --add-topic agents --add-topic portfolio \
  --homepage "https://mcp.alloc-context.com/llms.txt"
```

## Official MCP Registry

The canonical directory is [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io).
PulseMCP, Smithery, and other lists ingest from it.

This repo ships [`server.json`](../server.json) at the root with:

- **Remote:** `streamable-http` → `https://mcp.alloc-context.com/mcp`
- **Package:** PyPI `alloc-context` (stdio via `alloc-context mcp`) — publish to
  PyPI first; see [publishing.md](publishing.md).

### Publish steps

1. Ensure PyPI has the release — see [publishing.md](publishing.md).
   The package **README** must include `mcp-name: io.github.AllocContext/alloc-context`
   (registry ownership check against the PyPI long description).
2. **Automated (recommended):** every **release** run publishes after PyPI
   upload. For an out-of-band registry-only publish, Actions →
   **publish-mcp-registry** → Run workflow.
3. **Local (optional):**
   ```bash
   bash scripts/install-mcp-publisher.sh ~/.local/bin/mcp-publisher
   mcp-publisher login github
   bash scripts/publish-mcp-registry.sh ~/.local/bin/mcp-publisher
   ```
4. See the [MCP publishing guide](https://modelcontextprotocol.io/registry/publishing).

Verify after publish:

```bash
curl -sS "https://registry.modelcontextprotocol.io/v0/servers?search=AllocContext/alloc-context" | jq .
```

Namespace `io.github.AllocContext/alloc-context` requires GitHub auth as the repo owner.

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

Track stable inbound links here as directories pick up the listing.

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
