from __future__ import annotations

from dataclasses import dataclass

from alloccontext.ingest.wallet.chains import DEFAULT_WALLET_CHAIN_IDS


@dataclass(frozen=True)
class CuratedToken:
    contract: str
    symbol: str
    decimals: int


# Free-tier Etherscan tokenbalance lookups (addresstokenbalance is API Pro).
_CURATED_BY_CHAIN: dict[int, tuple[CuratedToken, ...]] = {
    1: (
        CuratedToken("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "USDC", 6),
        CuratedToken("0xdac17f958d2ee523a2206206994597c13d831ec7", "USDT", 6),
        CuratedToken("0x6b175474e89094c44da98b954eedeac495271d0f", "DAI", 18),
        CuratedToken("0x2260fac5e5542a773aa44fbcfedf7c193bc2c599", "WBTC", 8),
        CuratedToken("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "WETH", 18),
    ),
    42161: (
        CuratedToken("0xaf88d065e77c8cc2239327c5edb3a432268e5831", "USDC", 6),
        CuratedToken("0xff970a61a04b1ca14834a43f5de4533ebddb5cc8", "USDC", 6),
        CuratedToken("0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9", "USDT", 6),
        CuratedToken("0xda10009cbd5d07dd0cecc66161fc93d7c9000da1", "DAI", 18),
        CuratedToken("0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f", "WBTC", 8),
        CuratedToken("0x82af49447d8a07e3bd95bd0d56f35241523fbab1", "WETH", 18),
    ),
    8453: (
        CuratedToken("0x833589fcd6edb6e08f4c7c32d4f71b54bda02913", "USDC", 6),
        CuratedToken("0xd9aaec86b65d6f9524af1fdb8ae83789d97377ce", "USDC", 6),
        CuratedToken("0x4200000000000000000000000000000000000006", "WETH", 18),
        CuratedToken("0x2ae3f1ec7f1f5012cfeab0185bfc2aacee711e6", "CBETH", 18),
    ),
    10: (
        CuratedToken("0x0b2c639c533813c4aa6d0577d8ec5024ba0262b2", "USDC", 6),
        CuratedToken("0x7f5c764cbc14f9669b88837ca1490cca17c31607", "USDC", 6),
        CuratedToken("0x94b008aa00543c1307b0b1d40c0e6cbfc7971044", "USDT", 6),
        CuratedToken("0xda10009cbd5d07dd0cecc66161fc93d7c9000da1", "DAI", 18),
        CuratedToken("0x68f180fcce6831688e6282403cb1d48dc36a3d3", "WBTC", 8),
        CuratedToken("0x4200000000000000000000000000000000000006", "WETH", 18),
    ),
    137: (
        CuratedToken("0x3c499c542cef5e3811e1192ce70d8cc03d5c3359", "USDC", 6),
        CuratedToken("0x2791bca1f2de4661ed88a30c99a7a9449aa84174", "USDC", 6),
        CuratedToken("0xc2132d05d31c914a87c6611c10748aeb04b58e8f", "USDT", 6),
        CuratedToken("0x8f3cf7ad23cd3cadbd9735aff958023239c6a063", "DAI", 18),
        CuratedToken("0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6", "WBTC", 8),
        CuratedToken("0x7ceb23fd6bc0add59e62ac25578270cff1b9f619", "WETH", 18),
    ),
}


def curated_tokens_for_chain(chain_id: int) -> tuple[CuratedToken, ...]:
    return _CURATED_BY_CHAIN.get(chain_id, ())


def curated_tokens_for_chains(chain_ids: tuple[int, ...]) -> dict[int, tuple[CuratedToken, ...]]:
    return {chain_id: curated_tokens_for_chain(chain_id) for chain_id in chain_ids}


def default_curated_chain_ids() -> tuple[int, ...]:
    return DEFAULT_WALLET_CHAIN_IDS
