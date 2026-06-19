"""Classify bundle shift lines as market-wide vs sleeve (ADR-020)."""

from __future__ import annotations


def is_sleeve_shift(line: str) -> bool:
    cleaned = str(line).strip()
    if not cleaned:
        return False
    if cleaned.startswith("Portfolio Δ"):
        return True
    token = cleaned.split(None, 1)[0].upper()
    return token in {"BTC", "ETH", "CASH"} and " allocation " in cleaned


def split_notable_shifts(lines: list[str]) -> tuple[list[str], list[str]]:
    market: list[str] = []
    sleeve: list[str] = []
    for line in lines:
        text = str(line)
        if is_sleeve_shift(text):
            sleeve.append(text)
        else:
            market.append(text)
    return market, sleeve
