"""
Static configuration for Tectonic (Cronos mainnet) integration.

Phase 1 focuses on:
- Defining the on-chain addresses we intend to use
- Providing a single source of truth for RPC + contract metadata
- Allowing later runtime verification to fail fast if anything drifts
"""

from dataclasses import dataclass
from typing import List, Dict


@dataclass(frozen=True)
class TectonicAddresses:
    """Core contract addresses for Tectonic on Cronos mainnet."""

    # Primary trust anchor
    tonic: str = "0xDD73dEa10ABC2Bff99c60882EC5b2B81Bb1Dc5B2"

    # Underlying assets
    usdc: str = "0xc21223249CA28397B4B6541dfFaEcC539BfF0c59"

    # Money market contracts (Main Pool)
    tusdc: str = "0xB3bbf1bE947b245Aef26e3B6a9D777d7703F4c8e"  # tUSDC Main Pool
    comptroller: str = "0x7De56Bd8b37827c51835e162c867848fE2403a48"  # TectonicCore


@dataclass(frozen=True)
class NetworkConfig:
    name: str
    chain_id: int
    rpc_urls: List[str]


TECTONIC_NETWORK = NetworkConfig(
    name="cronos-mainnet",
    chain_id=25,
    rpc_urls=[
        # You can override these at runtime via the CRONOS_RPC env var if needed
        "https://evm.cronos.org",
        "https://cronos-evm.publicnode.com",
        "https://cronos.blockpi.network/v1/rpc/public",
    ],
)


TECTONIC_ADDRESSES = TectonicAddresses()


def as_dict() -> Dict[str, object]:
    """Helper to expose the config as a plain dict if needed."""
    return {
        "network": {
            "name": TECTONIC_NETWORK.name,
            "chain_id": TECTONIC_NETWORK.chain_id,
            "rpc_urls": list(TECTONIC_NETWORK.rpc_urls),
        },
        "addresses": {
            "TONIC": TECTONIC_ADDRESSES.tonic,
            "USDC": TECTONIC_ADDRESSES.usdc,
            "tUSDC": TECTONIC_ADDRESSES.tusdc,
            "Comptroller": TECTONIC_ADDRESSES.comptroller,
        },
    }


