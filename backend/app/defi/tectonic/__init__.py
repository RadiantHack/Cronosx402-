"""
Tectonic integration package for Cronos.

This package provides:
- Static config (addresses, RPCs)
- Contract verification utilities
- TectonicClient for supply/borrow/repay/redeem operations
- RiskEngine for health factor monitoring and safe borrow limits
"""

from .client import TectonicClient, TectonicError, AccountLiquidity
from .config import TECTONIC_ADDRESSES, TECTONIC_NETWORK
from .gas import GasStrategy, GasParams, create_gas_strategy
from .providers import ProviderManager, RPCProviderError, create_provider_manager
from .risk_engine import RiskEngine, RiskStatus, HealthMetrics, OraclePriceCheck

__all__ = [
    "TectonicClient",
    "TectonicError",
    "AccountLiquidity",
    "TECTONIC_ADDRESSES",
    "TECTONIC_NETWORK",
    "GasStrategy",
    "GasParams",
    "create_gas_strategy",
    "ProviderManager",
    "RPCProviderError",
    "create_provider_manager",
    "RiskEngine",
    "RiskStatus",
    "HealthMetrics",
    "OraclePriceCheck",
]

