from __future__ import annotations

from alloccontext.predictions.extract import extract_forward_watches


SAMPLE_BRIEF = """# Daily brief

## Portfolio snapshot
NAV $10k.

## Forward watches
- If CPI prints hot (above 0.3% MoM), watch whether BTC breaks below $95k by Friday.
- When Fear & Greed drops below 50, watch the ETH/BTC ratio before next week's brief.

## Observations
Hold steady.

## Not financial advice
"""


def test_extract_forward_watches_parses_natural_sentences() -> None:
    watches = extract_forward_watches(SAMPLE_BRIEF)
    assert len(watches) == 2
    assert watches[0].condition_text == "CPI prints hot (above 0.3% MoM)"
    assert watches[0].watch_text == "whether BTC breaks below $95k"
    assert watches[0].by_text == "Friday"
    assert watches[1].by_text == "next week's brief"


def test_extract_forward_watches_legacy_pipe_format() -> None:
    legacy = """## Forward watches
- IF CPI prints above 0.3% MoM | WATCH BTC breaks below 95k | BY Friday
"""
    watches = extract_forward_watches(legacy)
    assert len(watches) == 1
    assert watches[0].watch_text == "BTC breaks below 95k"


def test_extract_forward_watches_missing_section() -> None:
    assert extract_forward_watches("# Daily\n\nNo watches here.") == []
