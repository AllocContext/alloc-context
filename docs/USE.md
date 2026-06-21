# Use policy (plain language)

AllocContext is **source-available** under the [Elastic License 2.0](../LICENSE)
(ELv2). This page explains common scenarios in everyday terms. **The LICENSE
file is authoritative** if anything here differs.

**Primary path:** self-host — PyPI package, stdio MCP in Cursor, optional local
ingest. See [self-hosting.md](self-hosting.md) and [cursor-mcp.md](cursor-mcp.md).

The former official hosted MCP at `mcp.alloc-context.com` is **retired** (no
longer operated).

## Allowed without asking us

| Scenario | OK? |
|----------|-----|
| Run ingest + MCP on **your** VPS for **your** portfolio, briefs, or agents | Yes |
| Stdio MCP in Cursor; local bridge with `user.yaml` | Yes |
| Internal loopback HTTP MCP (no payment gate) for local dev or automation | Yes |
| Optional x402 on **your** host where **you** are the only consumer | Yes |
| Bridge that calls a **third-party** hosted AllocContext-compatible endpoint (you pay per call if they charge) | Yes |
| Modify the code for your own non-competing deployment | Yes |
| Open GitHub Issues and use the software locally | Yes |

Self-hosting is a **first-class** path — no license keys, no phone-home.

## Not allowed without separate permission

| Scenario | OK? |
|----------|-----|
| Offer AllocContext (or a derivative) as a **hosted or managed MCP service** to third parties — e.g. public `https://mcp.yoursite.com` with paid or free access for others | No (ELv2 limitation) |
| Imply your hosted MCP is **official** AllocContext | No (trademark / fair use) |
| Bulk relay or resale of paid access to a **third-party** hosted AllocContext endpoint | No (their terms + ELv2) |

The ELv2 restriction targets **competing hosted products**, not personal or
org-internal use on hardware you control.

## ELv2 “license key” clause

The LICENSE mentions license-key functionality. **AllocContext has no license
keys.** That clause does not apply; it is standard ELv2 boilerplate.

## Privacy (self-host)

When you self-host, portfolio and ingest data stay on hardware you control.
Optional live CEX reads are one-time per tool call — see
[user-config.md](user-config.md).

**Theses (`expectation_review`):** optional `theses[]` on `get_context_bundle`
are pass-through only — beliefs are not stored server-side. See
[mcp.md](mcp.md#privacy-theses-hosted-and-bridge).

## Competing hosted products

If you want to operate a **public paid MCP** built on this software for third
party customers, open a GitHub Issue to discuss — we may offer a separate
grant later. This is optional, not required for personal self-host.

## Related

- [LICENSE](../LICENSE) — Elastic License 2.0 (verbatim)
- [self-hosting.md](self-hosting.md) — VPS and systemd
- [mcp-http.md](mcp-http.md) — HTTP MCP and x402 (seller setup for **your** host)
