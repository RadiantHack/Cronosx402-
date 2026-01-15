"""
Configuration for Cronos x402 Payment System.

Loads and validates environment variables for Cronos network integration.
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class CronosConfig(BaseSettings):
    """Cronos network configuration."""
    
    # RPC Configuration
    cronos_rpc_url: str = os.getenv(
        "CRONOS_RPC_URL",
        "https://evm.cronos.org"  # Mainnet default
    )
    
    # Chain Configuration
    cronos_chain_id: int = int(os.getenv("CRONOS_CHAIN_ID", "25"))  # 25=mainnet, 338=testnet
    
    # Payment Configuration
    cronos_pay_to: str = os.getenv(
        "CRONOS_PAY_TO",
        ""
    )
    
    # Asset Configuration (native CRO or ERC20 contract address)
    cronos_asset: str = os.getenv(
        "CRONOS_ASSET",
        "CRO"  # Default to native CRO
    )
    
    # Optional timeout for payment verification
    cronos_max_timeout_seconds: Optional[int] = None
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False

    def validate(self) -> None:
        """Validate required configuration.
        
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        if not self.cronos_rpc_url:
            raise ValueError("CRONOS_RPC_URL environment variable is required")
        
        if not self.cronos_pay_to:
            raise ValueError("CRONOS_PAY_TO environment variable is required")
        
        if not self.cronos_pay_to.startswith("0x") or len(self.cronos_pay_to) != 42:
            raise ValueError(
                f"CRONOS_PAY_TO must be a valid Ethereum address: {self.cronos_pay_to}"
            )
        
        if self.cronos_chain_id not in [25, 338]:  # Mainnet and testnet
            raise ValueError(
                f"CRONOS_CHAIN_ID must be 25 (mainnet) or 338 (testnet), got {self.cronos_chain_id}"
            )


# Global config instance
cronos_config = CronosConfig()
