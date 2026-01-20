"""
Tectonic A2A Service Layer

Provides high-level service methods for Tectonic lending operations.
Wraps TectonicClient and RiskEngine to provide business logic.

This layer handles:
- Supply (deposit & collateral toggling)
- Borrowing with health factor checks
- Repayment operations
- Withdrawal with safety checks
- Position queries (supplied, borrowed, HF, liquidation buffer)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Tuple

from web3 import Web3

from ..defi.tectonic.client import TectonicClient, TectonicError, TectonicOperationError
from ..defi.tectonic.risk_engine import RiskEngine, HealthMetrics, RiskStatus

logger = logging.getLogger(__name__)


# --- Data Models -------------------------------------------------------

@dataclass
class SupplyRequest:
    """Request to supply USDC to Tectonic."""
    amount_usdc: Decimal  # Amount in USDC (will be converted to Wei)
    use_as_collateral: bool = True  # If True, will enterMarkets


@dataclass
class BorrowRequest:
    """Request to borrow USDC from Tectonic."""
    amount_usdc: Decimal  # Amount in USDC (will be converted to Wei)
    check_health_factor: bool = True  # If True, verify HF >= 1.2 after borrow


@dataclass
class RepayRequest:
    """Request to repay USDC borrow."""
    amount_usdc: Optional[Decimal] = None  # Amount in USDC; if None, repay all


@dataclass
class WithdrawRequest:
    """Request to withdraw USDC from supply."""
    amount_usdc: Optional[Decimal] = None  # Amount in USDC; if None, withdraw all


@dataclass
class PositionInfo:
    """Current state of a user's Tectonic position."""
    supplied_usdc: Decimal
    supplied_tusd_tokens: Decimal
    borrowed_usdc: Decimal
    available_liquidity_usdc: Decimal
    health_factor: Optional[Decimal]
    health_status: str  # "healthy", "warning", "critical", "liquidatable"
    safe_borrow_limit_usdc: Decimal
    liquidation_buffer_usdc: Decimal  # Distance to liquidation
    is_collateral_enabled: bool


@dataclass
class OperationResult:
    """Result of a Tectonic operation."""
    success: bool
    tx_hash: Optional[str] = None
    error_message: Optional[str] = None
    gas_used: Optional[int] = None
    position_after: Optional[PositionInfo] = None


# --- Tectonic Service ------------------------------------------------

class TectonicService:
    """High-level service for Tectonic lending operations."""

    def __init__(
        self,
        client: TectonicClient,
        risk_engine: Optional[RiskEngine] = None,
        safety_ltv: Decimal = Decimal("0.75"),
    ):
        """
        Initialize service with client and optional risk engine.
        
        Args:
            client: TectonicClient instance
            risk_engine: Optional RiskEngine for health checks
            safety_ltv: Safety LTV threshold (default 75%)
        """
        self.client = client
        self.risk_engine = risk_engine or RiskEngine(client, safety_ltv=safety_ltv)
        self.safety_ltv = safety_ltv
        self.decimals = 6  # USDC has 6 decimals

    # --- Utility Methods ---

    def _usdc_to_wei(self, amount: Decimal) -> int:
        """Convert USDC amount to Wei (accounting for 6 decimals)."""
        return int(amount * Decimal(10 ** self.decimals))

    def _wei_to_usdc(self, amount_wei: int) -> Decimal:
        """Convert Wei to USDC amount."""
        return Decimal(amount_wei) / Decimal(10 ** self.decimals)

    def _get_position_internal(self, address: Optional[str] = None) -> PositionInfo:
        """Internal: fetch raw position data."""
        try:
            # Get raw balances
            tusdc_balance = self.client.get_tusdc_balance(address)
            borrowed = self.client.get_borrow_balance(address)
            usdc_balance = self.client.get_usdc_balance(address)  # Wallet balance
            
            # Get liquidity info
            liquidity = self.client.get_account_liquidity(address)
            
            # Get markets entered
            markets = self.client.get_assets_in(address)
            tusdc_addr = self.client.web3.to_checksum_address(
                self.client.tusdc.address
            )
            is_collateral = tusdc_addr in [
                self.client.web3.to_checksum_address(m) for m in markets
            ]
            
            # Get health metrics from risk engine
            health_metrics = self.risk_engine.get_health_metrics(address)
            
            # Calculate liquidation buffer
            # This is how much more we can borrow before HF < 1.0
            liquidation_buffer = (
                health_metrics.available_liquidity_usd - 
                (health_metrics.available_liquidity_usd - health_metrics.shortfall_usd)
                if health_metrics.available_liquidity_usd > Decimal(0)
                else Decimal(0)
            )
            
            return PositionInfo(
                supplied_usdc=health_metrics.total_collateral_usd,
                supplied_tusd_tokens=self._wei_to_usdc(tusdc_balance),
                borrowed_usdc=health_metrics.total_borrow_usd,
                available_liquidity_usdc=health_metrics.available_liquidity_usd,
                health_factor=health_metrics.health_factor,
                health_status=health_metrics.status.value,
                safe_borrow_limit_usdc=health_metrics.safe_borrow_limit_usd,
                liquidation_buffer_usdc=liquidation_buffer,
                is_collateral_enabled=is_collateral,
            )
        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            raise

    # --- Core Operations ---

    def supply(self, request: SupplyRequest, address: Optional[str] = None) -> OperationResult:
        """
        Supply USDC to Tectonic.
        
        Args:
            request: SupplyRequest with amount and collateral flag
            address: Optional address (uses client's address if not provided)
            
        Returns:
            OperationResult with tx_hash and updated position
        """
        try:
            amount_wei = self._usdc_to_wei(request.amount_usdc)
            
            logger.info(f"Supplying {request.amount_usdc} USDC to Tectonic")
            
            # Supply USDC (mints tUSDC)
            receipt = self.client.supply_usdc(amount_wei)
            tx_hash = receipt.transactionHash.hex() if receipt.transactionHash else None
            gas_used = receipt.gasUsed
            
            # Enter markets if needed
            if request.use_as_collateral:
                try:
                    self.client.enter_markets_if_needed()
                except Exception as e:
                    logger.warning(f"Failed to enter markets: {e}")
                    # Not fatal; user may already be in markets
            
            # Fetch updated position
            position = self._get_position_internal(address)
            
            return OperationResult(
                success=True,
                tx_hash=tx_hash,
                gas_used=gas_used,
                position_after=position,
            )
        except (TectonicError, TectonicOperationError) as e:
            return OperationResult(
                success=False,
                error_message=str(e),
            )
        except Exception as e:
            logger.error(f"Supply failed: {e}")
            return OperationResult(
                success=False,
                error_message=f"Unexpected error: {str(e)}",
            )

    def borrow(self, request: BorrowRequest, address: Optional[str] = None) -> OperationResult:
        """
        Borrow USDC from Tectonic.
        
        Args:
            request: BorrowRequest with amount and health check flag
            address: Optional address
            
        Returns:
            OperationResult with tx_hash and updated position
        """
        try:
            amount_wei = self._usdc_to_wei(request.amount_usdc)
            
            # Health check before borrowing
            if request.check_health_factor:
                current_metrics = self.risk_engine.get_health_metrics(address)
                if current_metrics.health_factor and current_metrics.health_factor < Decimal("1.2"):
                    return OperationResult(
                        success=False,
                        error_message=f"Health factor too low: {current_metrics.health_factor}. Min required: 1.2",
                    )
                
                # Check if borrow would exceed safe limit
                new_total_borrow = current_metrics.total_borrow_usd + request.amount_usdc
                if new_total_borrow > current_metrics.safe_borrow_limit_usd:
                    return OperationResult(
                        success=False,
                        error_message=f"Borrow amount exceeds safe limit. Safe limit: {current_metrics.safe_borrow_limit_usd}, requested: {request.amount_usdc}",
                    )
            
            logger.info(f"Borrowing {request.amount_usdc} USDC from Tectonic")
            
            # Perform borrow
            receipt = self.client.borrow_usdc(amount_wei)
            tx_hash = receipt.transactionHash.hex() if receipt.transactionHash else None
            gas_used = receipt.gasUsed
            
            # Fetch updated position
            position = self._get_position_internal(address)
            
            return OperationResult(
                success=True,
                tx_hash=tx_hash,
                gas_used=gas_used,
                position_after=position,
            )
        except (TectonicError, TectonicOperationError) as e:
            return OperationResult(
                success=False,
                error_message=str(e),
            )
        except Exception as e:
            logger.error(f"Borrow failed: {e}")
            return OperationResult(
                success=False,
                error_message=f"Unexpected error: {str(e)}",
            )

    def repay(self, request: RepayRequest, address: Optional[str] = None) -> OperationResult:
        """
        Repay USDC borrow.
        
        Args:
            request: RepayRequest with optional amount (None = repay all)
            address: Optional address
            
        Returns:
            OperationResult with tx_hash and updated position
        """
        try:
            # Determine repay amount
            if request.amount_usdc is None:
                # Repay all: use max uint256
                amount_wei = 2**256 - 1
                logger.info("Repaying all USDC borrow")
            else:
                amount_wei = self._usdc_to_wei(request.amount_usdc)
                logger.info(f"Repaying {request.amount_usdc} USDC")
            
            # Perform repay
            receipt = self.client.repay_usdc(amount_wei)
            tx_hash = receipt.transactionHash.hex() if receipt.transactionHash else None
            gas_used = receipt.gasUsed
            
            # Fetch updated position
            position = self._get_position_internal(address)
            
            return OperationResult(
                success=True,
                tx_hash=tx_hash,
                gas_used=gas_used,
                position_after=position,
            )
        except (TectonicError, TectonicOperationError) as e:
            return OperationResult(
                success=False,
                error_message=str(e),
            )
        except Exception as e:
            logger.error(f"Repay failed: {e}")
            return OperationResult(
                success=False,
                error_message=f"Unexpected error: {str(e)}",
            )

    def withdraw(self, request: WithdrawRequest, address: Optional[str] = None) -> OperationResult:
        """
        Withdraw USDC from supply (redeem tUSDC).
        
        Args:
            request: WithdrawRequest with optional amount (None = withdraw all)
            address: Optional address
            
        Returns:
            OperationResult with tx_hash and updated position
        """
        try:
            # Get current position to calculate max withdrawal
            current_position = self._get_position_internal(address)
            
            # Determine withdrawal amount
            if request.amount_usdc is None:
                # Withdraw max available
                amount_wei = self._usdc_to_wei(current_position.supplied_usdc)
                logger.info("Withdrawing all supplied USDC")
            else:
                # Check if withdrawal would cause liquidation
                if current_position.health_factor and current_position.health_factor > Decimal(0):
                    projected_hf = (
                        current_position.health_factor * 
                        (current_position.supplied_usdc - request.amount_usdc) / 
                        current_position.supplied_usdc
                    ) if current_position.supplied_usdc > Decimal(0) else Decimal(0)
                    
                    if projected_hf < Decimal("1.1"):
                        return OperationResult(
                            success=False,
                            error_message=f"Withdrawal would cause liquidation. Projected HF: {projected_hf}",
                        )
                
                amount_wei = self._usdc_to_wei(request.amount_usdc)
                logger.info(f"Withdrawing {request.amount_usdc} USDC")
            
            # Perform redeem (redeem underlying by amount)
            receipt = self.client.redeem_usdc(amount_wei)
            tx_hash = receipt.transactionHash.hex() if receipt.transactionHash else None
            gas_used = receipt.gasUsed
            
            # Fetch updated position
            position = self._get_position_internal(address)
            
            return OperationResult(
                success=True,
                tx_hash=tx_hash,
                gas_used=gas_used,
                position_after=position,
            )
        except (TectonicError, TectonicOperationError) as e:
            return OperationResult(
                success=False,
                error_message=str(e),
            )
        except Exception as e:
            logger.error(f"Withdraw failed: {e}")
            return OperationResult(
                success=False,
                error_message=f"Unexpected error: {str(e)}",
            )

    def get_position(self, address: Optional[str] = None) -> PositionInfo:
        """
        Get current position info.
        
        Args:
            address: Optional address (uses client's address if not provided)
            
        Returns:
            PositionInfo with current state
        """
        return self._get_position_internal(address)
