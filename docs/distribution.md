# Distribution and discoverability

How AllocContext appears on GitHub, PyPI, the official MCP Registry, and curated
agent directories.

**Primary install:** PyPI `alloc-context` → stdio MCP (self-host). See
[cursor-mcp.md](cursor-mcp.md) and [self-hosting.md](self-hosting.md).

The former hosted endpoint `mcp.alloc-context.com` is **retired**.

## Short blurb (copy-paste)

```text
AllocContext — portfolio-aware crypto context for AI agents over MCP. Self-host
via PyPI (stdio MCP); optional local ingest for macro, regime, and market
rollups. Holdings from CEX read-only keys or a public EVM wallet;
holdings-scoped market, sentiment, macro, and regime; optional allocation
analysis. MIT license. GitHub: AllocContext/alloc-context
```

Architecture pattern: [deterministic-context-mcp-pattern.md](deterministic-context-mcp-pattern.md).

## GitHub repository metadata

| Field | Value |
|-------|-------|
| **Description** | Portfolio crypto context MCP for agents — self-host via PyPI; holdings-scoped market. MIT. |
| **Topics** | `mcp`, `bitcoin`, `ethereum`, `model-context-protocol`, `agents`, `portfolio` |
| **Website** | `https://github.com/AllocContext/alloc-context` |

Update via GitHub UI (gear next to About) or:

```bash
gh repo edit AllocContext/alloc-context \
  --description "Portfolio crypto context MCP for agents — self-host via PyPI; holdings-scoped market. MIT." \
  --add-topic mcp --add-topic bitcoin --add-topic ethereum \
  --add-topic model-context-protocol --add-topic agents --add-topic portfolio \
  --homepage "https://github.com/AllocContext/alloc-context"
```

## Official MCP Registry

The canonical directory is [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io).

This repo ships [`server.json`](../server.json) with:

- **Package:** PyPI `alloc-context` (stdio via `alloc-context mcp`) — see [publishing.md](publishing.md).
- **No remote URL** — official hosted MCP is retired.

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

After the first PyPI release, README and project URLs point at the GitHub repo.

## Other directories

| Directory | How to submit | Notes |
|-----------|---------------|-------|
| **MCP Registry** | `server.json` + `mcp-publisher` | Primary; package-only (stdio) |
| **PulseMCP** | Ingests registry; email if stale listing persists | Request removal/update after registry republish |
| **Smithery** | Dashboard update | Demote or remove hosted remote URL |
| **awesome-mcp** | PR to a maintained awesome list | Link `docs/cursor-mcp.md` |

## Related docs

| Doc | Purpose |
|-----|---------|
| [cursor-mcp.md](cursor-mcp.md) | Primary Cursor setup |
| [self-hosting.md](self-hosting.md) | Local ingest + MCP |
| [publishing.md](publishing.md) | PyPI + registry release workflow |
| [agent-integration.md](agent-integration.md) | Legacy hosted HTTP (retired) |
