from __future__ import annotations

import argparse
import json
import sys

from alloccontext.config import load_config
from alloccontext.ingest.runner import run_ingest
from alloccontext.rollup.context import build_context_bundle
from alloccontext.status_report import (
    build_status_report,
    default_mcp_health_url,
    format_status_report,
)
from alloccontext.store.db import connect


def cmd_ingest(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    conn = connect(config.paths.db)
    result = run_ingest(conn, config, dry_run=args.dry_run)
    conn.close()
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_rollup(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    conn = connect(config.paths.db)
    bundle = build_context_bundle(
        conn,
        config,
        scope=args.scope,
        rollup=config.rollup,
        save_snapshot=args.save,
    )
    conn.close()
    if args.stdout:
        print(json.dumps(bundle, indent=2))
    else:
        print(json.dumps({"ok": True, "bundle_id": bundle["bundle_id"]}, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    conn = connect(config.paths.db)
    try:
        report = build_status_report(
            config,
            conn,
            probe_mcp=not args.no_mcp,
            mcp_health_url=args.mcp_url,
            mcp_timeout_seconds=args.mcp_timeout,
        )
    finally:
        conn.close()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_status_report(report))
    return 0 if report.get("ok") else 1


def cmd_mcp(args: argparse.Namespace) -> int:
    if args.transport == "http":
        from alloccontext.mcp.http import run_http

        run_http(
            config_path=args.config,
            host=args.host,
            port=args.port,
            x402=args.x402,
        )
    else:
        from alloccontext.mcp.server import run_stdio

        run_stdio(config_path=args.config)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alloc-context")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Pull configured data sources")
    ingest_p.add_argument("--dry-run", action="store_true")
    ingest_p.set_defaults(func=cmd_ingest)

    rollup_p = sub.add_parser("rollup", help="Build ContextBundle JSON")
    rollup_p.add_argument("--scope", choices=["daily", "weekly"], default="daily")
    rollup_p.add_argument("--stdout", action="store_true")
    rollup_p.add_argument(
        "--save",
        action="store_true",
        help="Persist snapshot for delta chain (normally done by ingest)",
    )
    rollup_p.set_defaults(func=cmd_rollup)

    status_p = sub.add_parser(
        "status",
        help="Ingest ages, snapshot freshness, optional MCP /health probe",
    )
    status_p.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable JSON (default: human text for SSH)",
    )
    status_p.add_argument(
        "--no-mcp",
        action="store_true",
        help="Skip HTTP GET to MCP /health",
    )
    status_p.add_argument(
        "--mcp-url",
        default=None,
        help=f"MCP health URL (default: {default_mcp_health_url()})",
    )
    status_p.add_argument(
        "--mcp-timeout",
        type=float,
        default=5.0,
        help="Seconds to wait for MCP /health",
    )
    status_p.set_defaults(func=cmd_status)

    mcp_p = sub.add_parser("mcp", help="Run MCP server (stdio or HTTP)")
    mcp_p.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="stdio for Cursor; http for streamable MCP + optional x402",
    )
    mcp_p.add_argument("--host", default="127.0.0.1", help="HTTP bind host")
    mcp_p.add_argument("--port", type=int, default=8000, help="HTTP bind port")
    mcp_p.add_argument(
        "--x402",
        action="store_true",
        help="Require x402 USDC payment on HTTP (needs X402_PAY_TO)",
    )
    mcp_p.set_defaults(func=cmd_mcp)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
