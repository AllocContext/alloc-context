from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alloccontext.ingest.kalshi_files import KalshiTacticalSnapshot, load_tactical_snapshot


def extract_cf_price_history(raw: dict[str, Any]) -> dict[str, Any]:
    history = raw.get("cf_price_history")
    if isinstance(history, dict):
        return history
    return {}


def extract_market_quotes_from_state(raw: dict[str, Any]) -> list[dict[str, Any]]:
    by_ticker: dict[str, dict[str, Any]] = {}
    for source in ("opportunity_log_expiry", "journal_expiry"):
        for entry in raw.get(source) or []:
            ticker = entry.get("ticker")
            if not ticker:
                continue
            upper = str(ticker).upper()
            if not any(tag in upper for tag in ("BTCD", "ETHD", "15M")):
                continue
            yes_ask = entry.get("yes_ask_cents")
            no_ask = entry.get("no_ask_cents")
            if yes_ask is None and no_ask is None:
                continue
            ts = str(entry.get("at") or "")
            existing = by_ticker.get(str(ticker))
            if existing is None or ts >= str(existing.get("at") or ""):
                by_ticker[str(ticker)] = {
                    "ticker": str(ticker),
                    "yes_ask_cents": yes_ask,
                    "no_ask_cents": no_ask,
                    "at": ts,
                }
    return [
        {
            "ticker": row["ticker"],
            "yes_ask_cents": row.get("yes_ask_cents"),
            "no_ask_cents": row.get("no_ask_cents"),
        }
        for row in by_ticker.values()
    ]


def load_state_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) else None


def tactical_to_storage(snapshot: KalshiTacticalSnapshot, raw: dict[str, Any]) -> dict[str, Any]:
    cluster = raw.get("cluster") if isinstance(raw.get("cluster"), dict) else {}
    return {
        "ts": snapshot.at or raw.get("at"),
        "tape_summary": snapshot.tape_summary,
        "cluster_json": json.dumps(cluster),
        "raw_json": json.dumps(raw),
    }
