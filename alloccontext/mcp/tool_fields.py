"""Shared Pydantic Field metadata for MCP tool input schemas (Glama TDQS)."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

Scope = Annotated[
    str,
    Field(description="Rollup scope: daily (default) or weekly."),
]
Freshness = Annotated[
    str,
    Field(
        description=(
            "cached: read local ingest DB only. live: run ingest first "
            "(requires ingest API keys on the host)."
        ),
    ),
]
Assets = Annotated[
    list[str] | None,
    Field(
        description=(
            "Optional asset symbols to include in market fields "
            "(default BTC, ETH), e.g. ['BTC', 'ETH', 'HYPE']."
        ),
    ),
]
AllocationPct = Annotated[
    dict[str, float],
    Field(
        description=(
            "Current band weights keyed by asset (BTC, ETH, CASH); "
            "values typically sum to ~1."
        ),
    ),
]
TargetPct = Annotated[
    dict[str, float],
    Field(
        description=(
            "Target weights keyed by asset (BTC, ETH, CASH); "
            "values typically sum to ~1."
        ),
    ),
]
OptionalTargetPct = Annotated[
    dict[str, float] | None,
    Field(
        description=(
            "Optional target weights; when set, attaches allocation_analysis "
            "drift math to the response."
        ),
    ),
]
BandOptional = Annotated[
    float | None,
    Field(
        description=(
            "Drift band width as a fraction (e.g. 0.15 = 15% outside target)."
        ),
    ),
]
BandDefault = Annotated[
    float,
    Field(
        description="Drift band width as a fraction (default 0.15 = 15%).",
    ),
]
NavUsd = Annotated[
    float,
    Field(description="Portfolio net asset value in USD."),
]
Exchange = Annotated[
    str,
    Field(description="Spot exchange: kraken or coinbase."),
]
ExchangeKrakenDefault = Annotated[
    str,
    Field(description="Spot exchange for move wording: kraken (default) or coinbase."),
]
ApiKey = Annotated[
    str,
    Field(description="Read-only exchange API key (never stored by AllocContext)."),
]
ApiSecret = Annotated[
    str,
    Field(
        description=(
            "Read-only exchange API secret or Coinbase CDP private key "
            "(never stored)."
        ),
    ),
]
AsOf = Annotated[
    str,
    Field(description="ISO-8601 timestamp for the snapshot to load."),
]
MatchMode = Annotated[
    str,
    Field(
        description=(
            "exact: snapshot at as_of only. at_or_before (default): latest "
            "snapshot on or before as_of."
        ),
    ),
]
PriorAsOf = Annotated[
    str,
    Field(description="ISO-8601 timestamp of the earlier snapshot (required)."),
]
CurrentAsOf = Annotated[
    str | None,
    Field(
        description=(
            "ISO-8601 timestamp of the later snapshot; omit for latest live bundle."
        ),
    ),
]
Scenarios = Annotated[
    list[dict[str, Any]],
    Field(
        description=(
            "Scenario objects, each with required target_pct and optional name "
            "and band (default 0.15)."
        ),
    ),
]
