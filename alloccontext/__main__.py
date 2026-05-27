from __future__ import annotations

import argparse
import json
import sys

from alloccontext.config import load_config
from alloccontext.ingest.runner import run_ingest
from alloccontext.rollup.context import build_context_bundle
from alloccontext.store.db import SCHEMA_VERSION, connect
from alloccontext.store.status import ingest_status


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
    snapshot = ingest_status(conn)
    conn.close()
    payload = {
        "ok": True,
        "db": str(config.paths.db),
        "schema_version": SCHEMA_VERSION,
        "horizon_days": config.horizon.days,
        "ingest_sources_enabled": config.ingest.sources,
        **snapshot,
    }
    print(json.dumps(payload, indent=2))
    return 0


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

    status_p = sub.add_parser("status", help="Show ingest history and DB status")
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
