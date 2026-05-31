# Use policy (plain language)

AllocContext is **source-available** under the [Elastic License 2.0](../LICENSE)
(ELv2). This page explains common scenarios in everyday terms. **The LICENSE
file is authoritative** if anything here differs.

**Official hosted MCP:** `https://mcp.alloc-context.com/mcp`

## Allowed without asking us

| Scenario | OK? |
|----------|-----|
| Run ingest + MCP on **your** VPS for **your** portfolio, briefs, or agents | Yes |
| Stdio MCP in Cursor; local bridge with `user.yaml` | Yes |
| Internal loopback HTTP MCP (no payment gate) for operator or dev | Yes |
| Optional x402 on **your** host where **you** are the only consumer | Yes |
| Bridge that calls **official** hosted AllocContext (you pay x402 per call) | Yes |
| Modify the code for your own non-competing deployment | Yes |
| Open GitHub Issues and use the software locally | Yes |

Self-hosting is a **first-class** path — no license keys, no phone-home.

## Not allowed without separate permission

| Scenario | OK? |
|----------|-----|
| Offer AllocContext (or a derivative) as a **hosted or managed MCP service** to third parties — e.g. public `https://mcp.yoursite.com` with paid or free access for others | No (ELv2 limitation) |
| Imply your hosted MCP is **official** AllocContext | No (trademark / fair use) |
| Bulk relay or resale of paid access to **official** `mcp.alloc-context.com` | No (hosted terms) |

The ELv2 restriction targets **competing hosted products**, not personal or
org-internal use on hardware you control.

## ELv2 “license key” clause

The LICENSE mentions license-key functionality. **AllocContext has no license
keys.** That clause does not apply; it is standard ELv2 boilerplate.

## Privacy (hosted vs self-host)

When you use **official** hosted MCP or the default bridge upstream, see
[user-config.md](user-config.md) (when published) and ADR-007 privacy pillars:
nothing stored on shared infrastructure for pass-through portfolio reads;
one-time read-only; pass-through only.

When you **self-host**, portfolio data may exist in **your** SQLite if you run
ingest — that is your infrastructure, under your control.

## Commercial hosted MCP

If you want to operate a **public paid MCP** built on this software for third
party customers, open a GitHub Issue to discuss — we may offer a separate
grant later. This is optional, not required for personal self-host.

## Related

- [LICENSE](../LICENSE) — Elastic License 2.0 (verbatim)
- [self-hosting.md](self-hosting.md) — VPS and systemd
- [mcp-http.md](mcp-http.md) — HTTP MCP and x402 (seller setup for **your** host)
