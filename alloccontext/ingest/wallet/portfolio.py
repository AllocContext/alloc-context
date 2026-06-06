from __future__ import annotations

import re

from alloccontext.ingest.asset_registry import is_stable, normalize_canonical_symbol
from alloccontext.ingest.env_keys import optional_env_key
from alloccontext.ingest.kraken_portfolio import PortfolioSnapshot, portfolio_from_balances
from alloccontext.ingest.quote_resolver import QuoteResolverConfig, resolve_balance_prices
from alloccontext.ingest.wallet.chains import DEFAULT_WALLET_CHAIN_IDS, resolve_wallet_chains
from alloccontext.ingest.wallet.etherscan import EtherscanClient, EtherscanError
from alloccontext.timeutil import utc_now_iso

_WALLET_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

# Wrapped / bridged assets mapped to band symbols for allocation math.
_WRAPPED_SYMBOL_MAP: dict[str, str] = {
    "WETH": "ETH",
    "WBTC": "BTC",
    "BTCB": "BTC",
    "CBBTC": "BTC",
    "TBTC": "BTC",
    "RETH": "ETH",
    "STETH": "ETH",
    "WSTETH": "ETH",
    "CBETH": "ETH",
    "MATIC": "POL",
}


class WalletPortfolioError(Exception):
    pass


def validate_wallet_address(address: str) -> str:
    normalized = address.strip()
    if not _WALLET_ADDRESS_RE.match(normalized):
        raise ValueError("invalid_wallet_address")
    return normalized


def normalize_wallet_symbol(symbol: str) -> str:
    upper = normalize_canonical_symbol(symbol)
    return _WRAPPED_SYMBOL_MAP.get(upper, upper)


def _apply_stable_balances(
    raw_balances: dict[str, float],
) -> tuple[dict[str, float], dict[str, float]]:
    balances: dict[str, float] = {}
    cash_breakdown: dict[str, float] = {}
    for symbol, qty in raw_balances.items():
        if qty <= 0:
            continue
        if is_stable(symbol):
            balances["USD"] = balances.get("USD", 0.0) + qty
            cash_breakdown[symbol] = cash_breakdown.get(symbol, 0.0) + qty
        else:
            balances[symbol] = balances.get(symbol, 0.0) + qty
    return balances, cash_breakdown


def _filter_dust_balances(
    balances: dict[str, float],
    prices: dict[str, float],
    *,
    min_value_usd: float,
) -> dict[str, float]:
    if min_value_usd <= 0:
        return balances
    filtered: dict[str, float] = {}
    for symbol, qty in balances.items():
        if symbol == "USD":
            filtered[symbol] = qty
            continue
        price = prices.get(symbol)
        if price is None:
            filtered[symbol] = qty
            continue
        if qty * price >= min_value_usd:
            filtered[symbol] = qty
    return filtered


def _fetch_raw_balances(
    address: str,
    config,
    *,
    client: EtherscanClient | None = None,
) -> dict[str, float]:
    wallet_cfg = config.wallet
    if not wallet_cfg.enabled:
        raise WalletPortfolioError("wallet_read_disabled")

    api_key = optional_env_key("ETHERSCAN_API_KEY")
    if not api_key:
        raise WalletPortfolioError("missing_etherscan_api_key")

    chains = resolve_wallet_chains(wallet_cfg.chain_ids)
    etherscan = client or EtherscanClient(
        api_key,
        timeout_seconds=wallet_cfg.timeout_seconds,
        max_retries=wallet_cfg.max_retries,
        retry_backoff_seconds=wallet_cfg.retry_backoff_seconds,
    )

    raw_balances: dict[str, float] = {}
    skipped_chains: list[str] = []
    try:
        for chain in chains:
            try:
                native_qty = etherscan.native_balance_eth(chain.chain_id, address)
                if native_qty > 0:
                    symbol = chain.native_symbol
                    raw_balances[symbol] = raw_balances.get(symbol, 0.0) + native_qty
                for token in etherscan.curated_token_balances(chain.chain_id, address):
                    symbol = normalize_wallet_symbol(token.symbol)
                    raw_balances[symbol] = raw_balances.get(symbol, 0.0) + token.quantity
            except EtherscanError as exc:
                if _is_skippable_chain_error(exc):
                    skipped_chains.append(chain.label)
                    continue
                raise
    except EtherscanError as exc:
        raise WalletPortfolioError(str(exc)) from exc
    if not raw_balances and skipped_chains:
        raise WalletPortfolioError(
            "wallet_read_unsupported_chains: "
            + ",".join(skipped_chains)
        )
    return raw_balances


def _is_skippable_chain_error(exc: EtherscanError) -> bool:
    message = str(exc).lower()
    return (
        "not supported for this chain" in message
        or "upgrade your api plan" in message
        or "full chain coverage" in message
    )


def fetch_wallet_portfolio_snapshot(
    address: str,
    config,
    *,
    client: EtherscanClient | None = None,
    resolver_config: QuoteResolverConfig | None = None,
) -> PortfolioSnapshot:
    wallet_cfg = config.wallet
    normalized = validate_wallet_address(address)
    raw_balances = _fetch_raw_balances(normalized, config, client=client)
    balances, cash_breakdown = _apply_stable_balances(raw_balances)

    from alloccontext.ingest.quote_resolver import quote_resolver_config_from_app

    resolver = resolver_config or quote_resolver_config_from_app(config)
    prices = resolve_balance_prices(
        balances,
        {},
        exchange_price=lambda _symbol: None,
        resolver_config=resolver,
    )
    balances = _filter_dust_balances(
        balances,
        prices,
        min_value_usd=wallet_cfg.min_value_usd,
    )
    snap = portfolio_from_balances(balances, prices, cash_breakdown=cash_breakdown)
    return PortfolioSnapshot(
        ts=utc_now_iso(),
        nav_usd=snap.nav_usd,
        cash_usd=snap.cash_usd,
        btc_usd=snap.btc_usd,
        eth_usd=snap.eth_usd,
        btc_pct=snap.btc_pct,
        eth_pct=snap.eth_pct,
        cash_pct=snap.cash_pct,
        prices=snap.prices,
        cash_breakdown=snap.cash_breakdown,
        holdings=snap.holdings,
        unrecognized=snap.unrecognized,
    )


def default_wallet_chain_ids() -> tuple[int, ...]:
    return DEFAULT_WALLET_CHAIN_IDS
