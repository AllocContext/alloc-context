from __future__ import annotations

import argparse
import json
import sys

from alloccontext.brief.runner import run_brief
from alloccontext.config import load_config
from alloccontext.deliver.alerts import check_alerts
from alloccontext.ingest.runner import run_ingest
from alloccontext.review.monthly import run_monthly_review
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


def cmd_brief(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if not args.stdout and not args.email:
        args.stdout = True
    try:
        result = run_brief(
            config,
            scope=args.period,
            stdout=args.stdout,
            email=args.email,
        )
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    if not args.stdout:
        print(json.dumps(result, indent=2))
    return 0


def cmd_rollup(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    conn = connect(config.paths.db)
    bundle = build_context_bundle(
        conn,
        config,
        scope=args.scope,
        rollup=config.rollup,
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
        "alerts_enabled": config.deliver.alerts.enabled,
        **snapshot,
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if not args.stdout and not args.email:
        args.stdout = True
    conn = connect(config.paths.db)
    try:
        result = run_monthly_review(
            conn,
            config,
            month=args.month,
            stdout=args.stdout,
            email=args.email,
            apply=args.apply,
        )
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    finally:
        conn.close()
    if not args.stdout:
        print(json.dumps(result, indent=2))
    return 0


def cmd_alerts(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    conn = connect(config.paths.db)
    result = check_alerts(
        conn,
        config,
        email=args.email,
        stdout=args.stdout or not args.email,
    )
    conn.close()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alloc-context")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Pull configured data sources")
    ingest_p.add_argument("--dry-run", action="store_true")
    ingest_p.set_defaults(func=cmd_ingest)

    brief_p = sub.add_parser("brief", help="Build and deliver a market brief")
    brief_p.add_argument("period", choices=["daily", "weekly"])
    brief_p.add_argument("--stdout", action="store_true")
    brief_p.add_argument("--email", action="store_true", help="Send brief via email")
    brief_p.set_defaults(func=cmd_brief)

    rollup_p = sub.add_parser("rollup", help="Build ContextBundle JSON")
    rollup_p.add_argument("--scope", choices=["daily", "weekly"], default="daily")
    rollup_p.add_argument("--stdout", action="store_true")
    rollup_p.set_defaults(func=cmd_rollup)

    status_p = sub.add_parser("status", help="Show ingest and brief history")
    status_p.set_defaults(func=cmd_status)

    review_p = sub.add_parser("review", help="Review forward watches and brief quality")
    review_sub = review_p.add_subparsers(dest="review_kind", required=True)
    monthly_p = review_sub.add_parser("monthly", help="Monthly forward-watch review")
    monthly_p.add_argument(
        "--month",
        default=None,
        help="YYYY-MM (default: previous calendar month)",
    )
    monthly_p.add_argument("--stdout", action="store_true")
    monthly_p.add_argument("--email", action="store_true")
    monthly_p.add_argument(
        "--apply",
        action="store_true",
        help="Persist LLM prediction scores to the database",
    )
    monthly_p.set_defaults(func=cmd_review)

    alerts_p = sub.add_parser("alerts", help="Evaluate threshold alerts")
    alerts_p.add_argument("--stdout", action="store_true")
    alerts_p.add_argument("--email", action="store_true")
    alerts_p.set_defaults(func=cmd_alerts)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
