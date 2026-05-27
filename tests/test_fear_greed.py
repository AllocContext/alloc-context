from __future__ import annotations

from unittest.mock import patch

from alloccontext.ingest.fear_greed import classify_fear_greed, refresh_fear_greed


def test_classify_fear_greed() -> None:
    assert classify_fear_greed(10) == "Extreme Fear"
    assert classify_fear_greed(50) == "Neutral"
    assert classify_fear_greed(80) == "Extreme Greed"


def test_refresh_fear_greed_persists_rows(conn) -> None:
    sample = [
        {"timestamp": 1_700_000_000, "value": 72, "classification": "Greed"},
        {"timestamp": 1_699_913_600, "value": 40, "classification": "Fear"},
    ]
    with patch("alloccontext.ingest.fear_greed.fetch_fear_greed", return_value=sample):
        result = refresh_fear_greed(conn, history_limit=2)
    assert result["ok"] is True
    assert result["rows"] == 2
    row = conn.execute("SELECT value FROM fear_greed WHERE ts = ?", ("1700000000",)).fetchone()
    assert row["value"] == 72
