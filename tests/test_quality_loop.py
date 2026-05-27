from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch

from alloccontext.brief.runner import run_brief
from alloccontext.deliver.alerts import check_alerts, evaluate_rebalance_alert
from alloccontext.predictions.extract import ForwardWatch
from alloccontext.predictions.store import list_predictions, save_predictions
from alloccontext.review.monthly import run_monthly_review
from alloccontext.store.db import connect


def _portfolio_out_of_band() -> dict:
    return {
        "available": True,
        "nav_usd": 10000,
        "cash_usd": 2000,
        "allocation_pct": {"BTC": 0.55, "ETH": 0.25, "CASH": 0.20},
        "target_allocation_pct": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
        "drift": {"BTC": -0.15, "ETH": -0.05, "CASH": 0.20},
        "rebalance_hint": "consider_rebalance",
    }


def test_evaluate_rebalance_alert_fires(config) -> None:
    candidate = evaluate_rebalance_alert(_portfolio_out_of_band(), config)
    assert candidate is not None
    assert candidate["trigger_key"] == "rebalance_band"


def test_evaluate_rebalance_alert_within_band(config) -> None:
    portfolio = {
        "available": True,
        "rebalance_hint": "within_band",
    }
    assert evaluate_rebalance_alert(portfolio, config) is None


def test_check_alerts_suppressed_when_disabled(config, conn) -> None:
    result = check_alerts(conn, config, email=False, stdout=False)
    assert result["skipped"] is True


def test_check_alerts_delivers_when_enabled(config, conn, monkeypatch) -> None:
    cfg = replace(
        config,
        deliver=replace(
            config.deliver,
            alerts=replace(
                config.deliver.alerts,
                enabled=True,
            ),
        ),
    )
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "Analyst <onboarding@resend.dev>")
    monkeypatch.setenv("EMAIL_TO", "b@example.com")

    with patch("alloccontext.deliver.alerts.build_portfolio_context") as mock_portfolio:
        mock_portfolio.return_value = _portfolio_out_of_band()
        with patch("alloccontext.deliver.alerts.send_email") as mock_send:
            mock_send.return_value = {"provider": "resend", "id": "msg_123"}
            result = check_alerts(conn, cfg, email=True, stdout=False)

    assert result["fired"] is True
    assert result["delivered_via"] == "email"
    mock_send.assert_called_once()


def test_run_brief_logs_predictions(config, tmp_path, capsys) -> None:
    body = """# Daily brief

## Forward watches
- IF BTC closes below 90k | WATCH allocation drift | BY tomorrow

## Not financial advice
"""
    cfg = replace(
        config,
        paths=replace(config.paths, brief_archive_dir=tmp_path / "briefs"),
        synthesis=replace(config.synthesis, enabled=False),
    )
    as_of = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)

    with patch("alloccontext.brief.runner.synthesize_brief_markdown", return_value=body):
        result = run_brief(cfg, scope="daily", stdout=True, as_of=as_of)

    assert result["prediction_count"] == 1
    db_conn = connect(cfg.paths.db)
    rows = list_predictions(db_conn, month="2026-05")
    db_conn.close()
    assert len(rows) == 1
    assert rows[0]["watch_text"] == "allocation drift"


def test_monthly_review_without_llm(config, conn) -> None:
    conn.execute(
        """
        INSERT INTO brief_predictions(
          scope, brief_as_of, condition_text, watch_text, by_text,
          created_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "daily",
            "2026-04-15T12:00:00+00:00",
            "CPI hot",
            "BTC below 95k",
            "Friday",
            "2026-04-15T12:00:00+00:00",
            "open",
        ),
    )
    conn.execute(
        """
        INSERT INTO brief_archive(scope, as_of, context_json, body_markdown)
        VALUES (?, ?, ?, ?)
        """,
        ("daily", "2026-04-15T12:00:00+00:00", "{}", "# brief"),
    )
    conn.commit()

    cfg = replace(config, synthesis=replace(config.synthesis, enabled=False))
    result = run_monthly_review(
        conn,
        cfg,
        month="2026-04",
        stdout=False,
        email=False,
        apply=False,
        as_of=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
    )
    assert result["prediction_count"] == 1
    assert result["brief_stats"]["daily"] == 1


def test_monthly_review_apply_scores(config, conn) -> None:
    save_predictions(
        conn,
        scope="daily",
        brief_as_of="2026-04-10T12:00:00+00:00",
        watches=[
            ForwardWatch("CPI hot", "BTC below 95k", "Friday"),
        ],
    )
    row = conn.execute("SELECT id FROM brief_predictions").fetchone()
    pid = int(row["id"])
    conn.commit()

    def fake_llm(prompt, synthesis, *, system=None):
        return json.dumps([{"id": pid, "status": "miss", "notes": "BTC held above 95k."}])

    cfg = replace(config, synthesis=replace(config.synthesis, enabled=True))
    run_monthly_review(
        conn,
        cfg,
        month="2026-04",
        stdout=False,
        email=False,
        apply=True,
        llm_call=fake_llm,
        as_of=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
    )
    updated = conn.execute(
        "SELECT status, outcome_notes FROM brief_predictions WHERE id = ?",
        (pid,),
    ).fetchone()
    assert updated["status"] == "miss"
    assert "95k" in updated["outcome_notes"]


def test_save_predictions_preserves_reviewed_status(conn) -> None:
    watches = [ForwardWatch("CPI hot", "BTC below 95k", "Friday")]
    save_predictions(
        conn,
        scope="daily",
        brief_as_of="2026-05-21T12:00:00+00:00",
        watches=watches,
    )
    conn.execute(
        "UPDATE brief_predictions SET status = 'hit', outcome_notes = 'done' WHERE id = 1"
    )
    conn.commit()

    save_predictions(
        conn,
        scope="daily",
        brief_as_of="2026-05-21T12:00:00+00:00",
        watches=watches,
    )
    conn.commit()

    row = conn.execute(
        "SELECT status, outcome_notes FROM brief_predictions WHERE id = 1"
    ).fetchone()
    assert row["status"] == "hit"
    assert row["outcome_notes"] == "done"


def test_monthly_review_apply_ignores_foreign_ids(config, conn) -> None:
    save_predictions(
        conn,
        scope="daily",
        brief_as_of="2026-04-10T12:00:00+00:00",
        watches=[ForwardWatch("CPI hot", "BTC below 95k", "Friday")],
    )
    conn.execute(
        """
        INSERT INTO brief_predictions(
          scope, brief_as_of, condition_text, watch_text, by_text,
          created_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "daily",
            "2026-03-01T12:00:00+00:00",
            "Other",
            "Other watch",
            None,
            "2026-03-01T12:00:00+00:00",
            "open",
        ),
    )
    conn.commit()
    foreign_id = int(
        conn.execute(
            "SELECT id FROM brief_predictions WHERE brief_as_of LIKE '2026-03%'"
        ).fetchone()["id"]
    )

    def fake_llm(prompt, synthesis, *, system=None):
        return json.dumps(
            [{"id": foreign_id, "status": "miss", "notes": "Should not apply."}]
        )

    cfg = replace(config, synthesis=replace(config.synthesis, enabled=True))
    run_monthly_review(
        conn,
        cfg,
        month="2026-04",
        stdout=False,
        email=False,
        apply=True,
        llm_call=fake_llm,
        as_of=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
    )
    row = conn.execute(
        "SELECT status FROM brief_predictions WHERE id = ?", (foreign_id,)
    ).fetchone()
    assert row["status"] == "open"


def test_check_alerts_logs_suppressed_cooldown(config, conn) -> None:
    cfg = replace(
        config,
        deliver=replace(
            config.deliver,
            alerts=replace(config.deliver.alerts, enabled=True),
        ),
    )
    with patch("alloccontext.deliver.alerts.build_portfolio_context") as mock_portfolio:
        mock_portfolio.return_value = _portfolio_out_of_band()
        first = check_alerts(conn, cfg, email=False, stdout=True)
        second = check_alerts(conn, cfg, email=False, stdout=False)

    assert first["fired"] is True
    assert second["suppressed"] is True
    assert second["reason"] == "min_hours_between"
    count = conn.execute("SELECT COUNT(*) AS n FROM alert_log").fetchone()["n"]
    assert count == 2


def test_kraken_skips_without_credentials(config, conn, monkeypatch) -> None:
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    from alloccontext.ingest.kraken_portfolio import refresh_kraken

    result = refresh_kraken(conn, config)
    assert result["skipped"] is True
    assert result["ok"] is True


def test_etf_skips_without_data_source(config, conn, monkeypatch) -> None:
    monkeypatch.delenv("SOSOVALUE_API_KEY", raising=False)
    from alloccontext.ingest.etf_flows import refresh_etf_flows

    cfg = replace(
        config,
        etf=replace(config.etf, fallback_snapshot=None, sosovalue_enabled=True),
    )
    result = refresh_etf_flows(conn, cfg)
    assert result["skipped"] is True
    assert result["ok"] is True
