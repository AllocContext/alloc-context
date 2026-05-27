from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from alloccontext.synthesize.allocation_advice import (
    fallback_allocation_advice,
    synthesize_allocation_advice,
)


def _risk_off_context() -> dict:
    return {
        "portfolio": {
            "nav_usd": 10000.0,
            "allocation_pct": {"BTC": 0.55, "ETH": 0.25, "CASH": 0.20},
            "target_allocation_pct": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
            "rebalance_hint": "consider_rebalance",
        },
        "sentiment": {
            "available": True,
            "fear_greed": {"value": 22, "classification": "Fear"},
            "kalshi": {
                "available": True,
                "volatility_regime": "high",
                "tape_summary": "Tape today: broad down, high short vol, mixed hourly sentiment.",
            },
        },
        "market": {"available": True},
    }


def test_fallback_allocation_advice_includes_usd_moves(config) -> None:
    context = {
        "portfolio": {
            "nav_usd": 1000.0,
            "allocation_pct": {"BTC": 0.613, "ETH": 0.163, "CASH": 0.224},
        },
        "sentiment": {"fear_greed": {"value": 72}},
    }
    advice = fallback_allocation_advice(context, config, hint="consider_deploy_cash")
    assert "Moves to reach" in advice
    assert "Deploy ~$" in advice
    advice = fallback_allocation_advice(
        _risk_off_context(),
        config,
        hint="consider_trim_to_cash",
    )
    assert "consider shifting toward" in advice.lower()
    assert "BTC" in advice and "ETH" in advice and "Cash" in advice
    assert "50%" in advice


def test_fallback_allocation_advice_risk_on_uses_targets(config) -> None:
    context = {
        "sentiment": {
            "fear_greed": {"value": 72},
            "kalshi": {
                "volatility_regime": "low",
                "tape_summary": "Tape today: broad up, calm short vol, crowd leaning YES on hourly.",
            },
        }
    }
    advice = fallback_allocation_advice(
        context,
        config,
        hint="consider_deploy_cash",
    )
    assert "70%" in advice
    assert "30%" in advice


def test_synthesize_allocation_advice_uses_llm_when_available(config, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_llm(prompt, synthesis, *, system=None):
        assert "rebalance_hint" in prompt
        assert "ContextBundle" in system or "ContextBundle" in prompt
        return (
            "Both BTC and ETH look risk-on. Consider shifting toward "
            "BTC 35%, ETH 15%, Cash 50% while volatility stays elevated."
        )

    advice = synthesize_allocation_advice(
        _risk_off_context(),
        config,
        hint="consider_rebalance",
        llm_call=fake_llm,
    )
    assert "BTC 35%" in advice


def test_synthesize_allocation_advice_falls_back_on_llm_error(config, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def failing_llm(prompt, synthesis, *, system=None):
        raise TimeoutError("timed out")

    advice = synthesize_allocation_advice(
        _risk_off_context(),
        config,
        hint="consider_rebalance",
        llm_call=failing_llm,
    )
    assert "consider shifting toward" in advice.lower()


def test_check_alerts_email_includes_allocation_advice(config, conn, monkeypatch) -> None:
    from alloccontext.deliver.alerts import check_alerts

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
        mock_portfolio.return_value = {
            "available": True,
            "nav_usd": 10000,
            "cash_usd": 2000,
            "allocation_pct": {"BTC": 0.55, "ETH": 0.25, "CASH": 0.20},
            "target_allocation_pct": {"BTC": 0.70, "ETH": 0.30, "CASH": 0.0},
            "drift": {"BTC": -0.15, "ETH": -0.05, "CASH": 0.20},
            "rebalance_hint": "consider_rebalance",
        }
        with patch(
            "alloccontext.deliver.alerts.synthesize_allocation_advice",
            return_value="Consider shifting toward BTC 35%, ETH 15%, Cash 50%.",
        ):
            with patch("alloccontext.deliver.alerts.send_email") as mock_send:
                mock_send.return_value = {"provider": "resend", "id": "msg_123"}
                result = check_alerts(conn, cfg, email=True, stdout=False)

    assert result["fired"] is True
    body = mock_send.call_args.kwargs["body"]
    assert "Suggested allocation" in body
    assert "BTC 35%" in body
