from __future__ import annotations

from dataclasses import dataclass

# ADR-012 D1: EVM mainnet + major L2s (deterministic, bounded set).
DEFAULT_WALLET_CHAIN_IDS: tuple[int, ...] = (1, 42161, 8453, 10, 137)


@dataclass(frozen=True)
class EvmChain:
    chain_id: int
    label: str
    native_symbol: str


EVM_CHAINS: dict[int, EvmChain] = {
    1: EvmChain(chain_id=1, label="ethereum", native_symbol="ETH"),
    42161: EvmChain(chain_id=42161, label="arbitrum", native_symbol="ETH"),
    8453: EvmChain(chain_id=8453, label="base", native_symbol="ETH"),
    10: EvmChain(chain_id=10, label="optimism", native_symbol="ETH"),
    137: EvmChain(chain_id=137, label="polygon", native_symbol="POL"),
}


def resolve_wallet_chains(chain_ids: tuple[int, ...]) -> tuple[EvmChain, ...]:
    unknown = [chain_id for chain_id in chain_ids if chain_id not in EVM_CHAINS]
    if unknown:
        raise ValueError(f"unsupported wallet chain_ids: {unknown}")
    return tuple(EVM_CHAINS[chain_id] for chain_id in chain_ids)
