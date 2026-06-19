from __future__ import annotations

from alloccontext.rollup.shift_classification import is_sleeve_shift, split_notable_shifts


def test_is_sleeve_shift_allocation_and_nav() -> None:
    assert is_sleeve_shift("BTC allocation +2.1 pp")
    assert is_sleeve_shift("Portfolio Δ $+500.00 since prior snapshot")
    assert not is_sleeve_shift("BTC +2.10% since prior snapshot")
    assert not is_sleeve_shift("F&G 68 → 52 (-16)")


def test_split_notable_shifts() -> None:
    market, sleeve = split_notable_shifts(
        [
            "BTC +2.10% since prior snapshot",
            "ETH allocation -1.5 pp",
            "F&G 68 → 52 (-16)",
        ]
    )
    assert market == ["BTC +2.10% since prior snapshot", "F&G 68 → 52 (-16)"]
    assert sleeve == ["ETH allocation -1.5 pp"]
