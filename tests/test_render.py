from __future__ import annotations

from alloccontext.deliver.render import markdown_to_html, markdown_to_plain


SAMPLE_BRIEF = """# Daily brief

## Portfolio snapshot
NAV **$10,250** with `70/30` BTC/ETH target.

## Forward watches
- If CPI prints hot (above 0.3% MoM), watch whether BTC breaks below $95k by Friday.
- When Fear & Greed drops below 50, watch the ETH/BTC ratio before next week's brief.

## Observations
Hold steady — no urgent action.

## Not financial advice
"""


def test_markdown_to_plain_strips_markup_and_formats_sections() -> None:
    plain = markdown_to_plain(SAMPLE_BRIEF)
    assert "DAILY BRIEF" in plain
    assert "##" not in plain
    assert "**" not in plain
    assert "`" not in plain
    assert "Portfolio snapshot" in plain
    assert "• If CPI prints hot" in plain
    assert "watch whether BTC breaks below $95k by Friday." in plain
    assert "Hold steady — no urgent action." in plain


def test_markdown_to_html_uses_headings_and_lists() -> None:
    html = markdown_to_html(SAMPLE_BRIEF)
    assert "<h1" in html and "Daily brief" in html
    assert "<h2" in html and "Portfolio snapshot" in html
    assert "<ul" in html and "<li>" in html
    assert "<strong>$10,250</strong>" in html
    assert "<code>70/30</code>" in html
    assert "If CPI prints hot" in html
    assert "<!DOCTYPE html>" in html
