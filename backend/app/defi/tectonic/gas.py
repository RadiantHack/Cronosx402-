"""
Phase 5: EIP-1559 Gas Strategy for Cronos.

This module provides:
- Dynamic base fee calculation from fee history
- Priority fee (tip) estimation for Cronos
- maxFeePerGas computation with safety multipliers
- Centralized gas estimation and transaction building
- Reusable for both Tectonic and swap operations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from web3 import Web3
from web3.types import Wei

logger = logging.getLogger(__name__)

# Default gas limit if estimation fails
DEFAULT_GAS_LIMIT = 300000

# Safety multiplier for base fee (ensures tx remains valid even if base fee rises)
BASE_FEE_MULTIPLIER = 2.0  # 2x base fee

# Default priority fee (tip) in gwei for Cronos
DEFAULT_PRIORITY_FEE_GWEI = 0.1

# Minimum priority fee
MIN_PRIORITY_FEE_GWEI = 0.01

# Maximum priority fee (safety cap)
MAX_PRIORITY_FEE_GWEI = 10.0


@dataclass
class GasParams:
    """Gas parameters for EIP-1559 transactions."""

    max_fee_per_gas: Wei  # maxFeePerGas (baseFee * multiplier + priorityFee)
    max_priority_fee_per_gas: Wei  # maxPriorityFeePerGas (tip)
    gas_limit: int  # Gas limit for the transaction


class GasStrategyError(Exception):
    """Base exception for gas strategy errors."""

    pass


class GasStrategy:
    """
    EIP-1559 gas strategy for Cronos transactions.

    Calculates optimal gas prices based on:
    - Current base fee from fee history
    - Priority fee (tip) for fast inclusion
    - Safety multipliers to handle base fee spikes
    """

    def __init__(
        self,
        web3: Web3,
        base_fee_multiplier: float = BASE_FEE_MULTIPLIER,
        default_priority_fee_gwei: float = DEFAULT_PRIORITY_FEE_GWEI,
    ) -> None:
        """
        Initialize the gas strategy.

        Args:
            web3: Web3 instance connected to Cronos
            base_fee_multiplier: Multiplier for base fee (default: 2.0)
            default_priority_fee_gwei: Default priority fee in gwei (default: 0.1)
        """
        self.web3 = web3
        self.base_fee_multiplier = base_fee_multiplier
        self.default_priority_fee_gwei = default_priority_fee_gwei

    def get_base_fee(self, block_number: Optional[int] = None) -> Wei:
        """
        Get the current base fee from the latest block or fee history.

        Args:
            block_number: Optional block number to query (defaults to 'latest')

        Returns:
            Base fee in Wei

        Raises:
            GasStrategyError: If base fee cannot be determined
        """
        try:
            # Try to get base fee from latest block
            if block_number is None:
                block_number = self.web3.eth.block_number

            block = self.web3.eth.get_block(block_number, full_transactions=False)
            if hasattr(block, "baseFeePerGas") and block.baseFeePerGas is not None:
                return Wei(block.baseFeePerGas)

            # Fallback: try fee history API
            try:
                fee_history = self.web3.eth.fee_history(1, "latest", ["baseFeePerGas"])
                if fee_history and "baseFeePerGas" in fee_history and fee_history["baseFeePerGas"]:
                    base_fees = fee_history["baseFeePerGas"]
                    if base_fees and len(base_fees) > 0:
                        return Wei(int(base_fees[-1]))
            except Exception as e:
                logger.debug(f"Fee history API not available: {e}")

            # Last resort: estimate from gas price (divide by 2 as rough estimate)
            gas_price = self.web3.eth.gas_price
            estimated_base_fee = Wei(gas_price // 2)
            logger.warning(f"Could not get base fee, estimating as {estimated_base_fee} wei from gas_price")
            return estimated_base_fee

        except Exception as e:
            raise GasStrategyError(f"Failed to get base fee: {e}") from e

    def get_priority_fee(self) -> Wei:
        """
        Get the priority fee (tip) for fast transaction inclusion.

        For Cronos, we use a simple strategy:
        - Try to get maxPriorityFeePerGas from the network
        - Fall back to a default value

        Returns:
            Priority fee in Wei
        """
        try:
            # Try to get maxPriorityFeePerGas from the network
            max_priority_fee = self.web3.eth.max_priority_fee
            if max_priority_fee:
                # Ensure it's within reasonable bounds
                max_priority_gwei = self.web3.from_wei(max_priority_fee, "gwei")
                if MIN_PRIORITY_FEE_GWEI <= max_priority_gwei <= MAX_PRIORITY_FEE_GWEI:
                    return Wei(max_priority_fee)

            # Fallback to default
            default_priority_wei = self.web3.to_wei(self.default_priority_fee_gwei, "gwei")
            logger.debug(f"Using default priority fee: {self.default_priority_fee_gwei} gwei")
            return Wei(default_priority_wei)

        except Exception as e:
            # Fallback to default if network doesn't support it
            logger.debug(f"Could not get maxPriorityFeePerGas, using default: {e}")
            default_priority_wei = self.web3.to_wei(self.default_priority_fee_gwei, "gwei")
            return Wei(default_priority_wei)

    def calculate_gas_params(
        self,
        gas_limit: Optional[int] = None,
        block_number: Optional[int] = None,
    ) -> GasParams:
        """
        Calculate optimal gas parameters for an EIP-1559 transaction.

        Formula:
            maxFeePerGas = (baseFee * multiplier) + priorityFee
            maxPriorityFeePerGas = priorityFee

        Args:
            gas_limit: Optional gas limit (will estimate if not provided)
            block_number: Optional block number for base fee lookup

        Returns:
            GasParams with maxFeePerGas, maxPriorityFeePerGas, and gas_limit
        """
        # Get base fee and priority fee
        base_fee = self.get_base_fee(block_number)
        priority_fee = self.get_priority_fee()

        # Calculate maxFeePerGas with safety multiplier
        base_fee_with_multiplier = int(base_fee * self.base_fee_multiplier)
        max_fee_per_gas = Wei(base_fee_with_multiplier + priority_fee)

        # Use provided gas limit or default
        if gas_limit is None:
            gas_limit = DEFAULT_GAS_LIMIT

        logger.debug(
            f"Gas params: baseFee={base_fee} wei, priorityFee={priority_fee} wei, "
            f"maxFeePerGas={max_fee_per_gas} wei, gasLimit={gas_limit}"
        )

        return GasParams(
            max_fee_per_gas=max_fee_per_gas,
            max_priority_fee_per_gas=priority_fee,
            gas_limit=gas_limit,
        )

    def estimate_and_build_tx(
        self,
        contract_function,
        from_address: str,
        value: int = 0,
        tx_overrides: Optional[dict] = None,
    ) -> dict:
        """
        Estimate gas and build a transaction with optimal EIP-1559 parameters.

        Args:
            contract_function: Web3 contract function to call
            from_address: Sender address
            value: Optional value to send (for payable functions)
            tx_overrides: Optional dict of transaction overrides

        Returns:
            Transaction dict ready for signing

        Raises:
            GasStrategyError: If gas estimation fails
        """
        # Build base transaction
        base_tx = {
            "from": from_address,
            "value": value,
        }
        if tx_overrides:
            base_tx.update(tx_overrides)

        # Estimate gas
        try:
            estimated_gas = contract_function.estimate_gas(base_tx)
            # Add 20% buffer for safety
            gas_limit = int(estimated_gas * 1.2)
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}. Using default gas limit.")
            gas_limit = DEFAULT_GAS_LIMIT

        # Get gas parameters
        gas_params = self.calculate_gas_params(gas_limit=gas_limit)

        # Build final transaction
        tx = contract_function.build_transaction(
            {
                **base_tx,
                "gas": gas_params.gas_limit,
                "maxFeePerGas": gas_params.max_fee_per_gas,
                "maxPriorityFeePerGas": gas_params.max_priority_fee_per_gas,
            }
        )

        return tx

    def get_gas_summary(self) -> dict:
        """
        Get a summary of current gas conditions.

        Returns:
            Dictionary with current gas prices and parameters
        """
        try:
            base_fee = self.get_base_fee()
            priority_fee = self.get_priority_fee()
            gas_params = self.calculate_gas_params()

            return {
                "base_fee_wei": base_fee,
                "base_fee_gwei": self.web3.from_wei(base_fee, "gwei"),
                "priority_fee_wei": priority_fee,
                "priority_fee_gwei": self.web3.from_wei(priority_fee, "gwei"),
                "max_fee_per_gas_wei": gas_params.max_fee_per_gas,
                "max_fee_per_gas_gwei": self.web3.from_wei(gas_params.max_fee_per_gas, "gwei"),
                "base_fee_multiplier": self.base_fee_multiplier,
            }
        except Exception as e:
            return {"error": str(e)}


def create_gas_strategy(web3: Web3, **kwargs) -> GasStrategy:
    """
    Factory function to create a GasStrategy with sensible defaults.

    Args:
        web3: Web3 instance connected to Cronos
        **kwargs: Optional arguments to pass to GasStrategy constructor

    Returns:
        Configured GasStrategy instance
    """
    return GasStrategy(web3, **kwargs)

