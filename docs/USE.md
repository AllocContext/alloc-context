# Use policy (plain language)

AllocContext is open source under the [MIT License](../LICENSE). **The LICENSE
file is authoritative** if anything here differs.

**How we ship it:** self-host — install from PyPI, run stdio MCP in Cursor,
optional local ingest. See [self-hosting.md](self-hosting.md) and
[cursor-mcp.md](cursor-mcp.md).

We do not operate a hosted MCP service. If you run AllocContext on your own
hardware, that deployment is yours to operate and describe.

## Trademark

Do not imply your deployment is the official AllocContext service unless it is
operated by AllocContext.

## Privacy (self-host)

When you self-host, portfolio and ingest data stay on hardware you control.
Optional live CEX reads are one-time per tool call — see
[user-config.md](user-config.md).

**Theses (`expectation_review`):** optional `theses[]` on `get_context_bundle`
are pass-through only — beliefs are not stored server-side. See
[mcp.md](mcp.md#privacy-theses-hosted-and-bridge).

## Related

- [LICENSE](../LICENSE) — MIT License
- [self-hosting.md](self-hosting.md) — local ingest + MCP
- [mcp-http.md](mcp-http.md) — optional HTTP MCP on your host
