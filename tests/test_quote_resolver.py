from __future__ import annotations

import pytest

from alloccontext.ingest.asset_registry import coingecko_ids_for_symbols, symbols_needing_quotes
from alloccontext.ingest.quote_resolver import (
    QuoteResolverConfig,
    parse_cmc_symbol_prices,
    quote_resolver_config_from_app,
    resolve_balance_prices,
)


def test_symbols_needing_quotes_skips_stables_and_zero() -> None:
    balances = {"BTC": 1.0, "USDC": 100.0, "HYPE": 0.0, "ETH": 2.0}
    assert symbols_needing_quotes(balances) == ["BTC", "ETH"]


def test_coingecko_ids_for_symbols_maps_hype() -> None:
    coin_ids, id_to_symbol = coingecko_ids_for_symbols(["HYPE", "UNKNOWN"])
    assert coin_ids == ["hyperliquid"]
    assert id_to_symbol == {"hyperliquid": "HYPE"}


def test_parse_cmc_symbol_prices() -> None:
    quotes = {
        "HYPE": {
            "symbol": "HYPE",
            "quote": {"USD": {"price": "42.5"}},
        },
        "BAD": {"quote": "nope"},
    }
    assert parse_cmc_symbol_prices(quotes) == {"HYPE": pytest.approx(42.5)}


def test_parse_cmc_symbol_prices_uses_payload_symbol_not_dict_key() -> None:
    """CMC API keys `data` by numeric id; symbol lives on the asset object."""
    quotes = {
        "32196": {
            "symbol": "HYPE",
            "quote": {"USD": {"price": 38.0}},
        },
    }
    assert parse_cmc_symbol_prices(quotes) == {"HYPE": pytest.approx(38.0)}


def test_resolve_balance_prices_ignores_non_positive_spot_marks() -> None:
    calls: list[str] = []

    def exchange_price(symbol: str) -> float | None:
        calls.append(symbol)
        return 100.0 if symbol == "BTC" else None

    prices = resolve_balance_prices(
        {"BTC": 1.0},
        {"BTC": 0.0},
        exchange_price=exchange_price,
        resolver_config=QuoteResolverConfig(),
    )
    assert prices["BTC"] == pytest.approx(100.0)
    assert calls == ["BTC"]


def test_resolve_balance_prices_uses_spot_then_exchange() -> None:
    calls: list[str] = []

    def exchange_price(symbol: str) -> float | None:
        calls.append(symbol)
        return {"SOL": 150.0}.get(symbol)

    prices = resolve_balance_prices(
        {"BTC": 1.0, "SOL": 2.0},
        {"BTC": 100_000.0},
        exchange_price=exchange_price,
        resolver_config=QuoteResolverConfig(),
    )
    assert prices["BTC"] == pytest.approx(100_000.0)
    assert prices["SOL"] == pytest.approx(150.0)
    assert calls == ["SOL"]


def test_resolve_balance_prices_falls_back_to_cmc(monkeypatch) -> None:
    def fake_cmc(*, symbols, api_key, timeout):  # noqa: ARG001
        assert symbols == ["HYPE"]
        return {
            "HYPE": {
                "symbol": "HYPE",
                "quote": {"USD": {"price": "33.0"}},
            }
        }

    monkeypatch.setattr(
        "alloccontext.ingest.coinmarketcap.fetch_cmc_quotes",
        fake_cmc,
    )

    prices = resolve_balance_prices(
        {"HYPE": 10.0},
        {},
        exchange_price=lambda _symbol: None,
        resolver_config=QuoteResolverConfig(coinmarketcap_api_key="test-key"),
    )
    assert prices["HYPE"] == pytest.approx(33.0)


def test_resolve_balance_prices_falls_back_to_coingecko(monkeypatch) -> None:
    def fake_cg(*, coin_ids, api_key, timeout):  # noqa: ARG001
        assert coin_ids == ["hyperliquid"]
        return {"hyperliquid": 25.0}

    monkeypatch.setattr(
        "alloccontext.ingest.coingecko.fetch_coingecko_simple_prices",
        fake_cg,
    )

    prices = resolve_balance_prices(
        {"HYPE": 5.0},
        {},
        exchange_price=lambda _symbol: None,
        resolver_config=QuoteResolverConfig(coingecko_api_key="test-key"),
    )
    assert prices["HYPE"] == pytest.approx(25.0)


def test_resolve_balance_prices_cmc_before_coingecko(monkeypatch) -> None:
    """CMC wins when both APIs would return a mark."""

    def fake_cmc(*, symbols, api_key, timeout):  # noqa: ARG001
        return {
            "HYPE": {
                "symbol": "HYPE",
                "quote": {"USD": {"price": "40.0"}},
            }
        }

    def fake_cg(*, coin_ids, api_key, timeout):  # noqa: ARG001
        raise AssertionError("CoinGecko should not run when CMC succeeds")

    monkeypatch.setattr(
        "alloccontext.ingest.coinmarketcap.fetch_cmc_quotes",
        fake_cmc,
    )
    monkeypatch.setattr(
        "alloccontext.ingest.coingecko.fetch_coingecko_simple_prices",
        fake_cg,
    )

    prices = resolve_balance_prices(
        {"HYPE": 1.0},
        {},
        exchange_price=lambda _symbol: None,
        resolver_config=QuoteResolverConfig(
            coinmarketcap_api_key="cmc",
            coingecko_api_key="cg",
        ),
    )
    assert prices["HYPE"] == pytest.approx(40.0)


def test_resolve_balance_prices_leaves_symbol_unpriced_when_all_sources_fail(
    monkeypatch,
) -> None:
    def fake_cmc(**kwargs):  # noqa: ARG001
        raise RuntimeError("cmc down")

    def fake_cg(**kwargs):  # noqa: ARG001
        raise RuntimeError("cg down")

    monkeypatch.setattr(
        "alloccontext.ingest.coinmarketcap.fetch_cmc_quotes",
        fake_cmc,
    )
    monkeypatch.setattr(
        "alloccontext.ingest.coingecko.fetch_coingecko_simple_prices",
        fake_cg,
    )

    prices = resolve_balance_prices(
        {"HYPE": 1.0},
        {},
        exchange_price=lambda _symbol: None,
        resolver_config=QuoteResolverConfig(
            coinmarketcap_api_key="cmc",
            coingecko_api_key="cg",
        ),
    )
    assert prices == {}


def test_quote_resolver_config_from_app(config, monkeypatch) -> None:
    monkeypatch.setenv("COINMARKETCAP_API_KEY", "cmc-key")
    monkeypatch.setenv("COINGECKO_API_KEY", "cg-key")
    resolved = quote_resolver_config_from_app(config)
    assert resolved.coinmarketcap_api_key == "cmc-key"
    assert resolved.coingecko_api_key == "cg-key"
    assert resolved.timeout_seconds >= 20.0
