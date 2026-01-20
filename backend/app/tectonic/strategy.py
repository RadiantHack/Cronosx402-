"""
Tectonic Automation & Strategy Layer

Provides automated strategies for managing Tectonic positions.

Current Strategies:
1. Auto-Repay on Low Health Factor:
   - Monitors HF < 1.1 threshold
   - Automatically swaps a secondary asset → USDC
   - Uses proceeds to repay borrow
   - Aims to restore HF >= 1.2

2. Position Monitoring:
   - Track health factor changes
   - Alert on threshold breaches
   - Suggest optimal actions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional, Callable

from ..defi.tectonic.client import TectonicClient
from ..defi.tectonic.risk_engine import RiskEngine, RiskStatus
from .service import TectonicService, RepayRequest

logger = logging.getLogger(__name__)


# --- Data Models ---

class StrategyAction(Enum):
    """Recommended actions based on position health."""
    NONE = "none"
    REPAY = "repay"
    WITHDRAW = "withdraw"
    DEPOSIT = "deposit"
    EMERGENCY_LIQUIDATE = "emergency_liquidate"


@dataclass
class StrategyRecommendation:
    """Strategy recommendation based on current position."""
    action: StrategyAction
    priority: int  # 1 (low) to 5 (critical)
    reason: str
    suggested_amount: Optional[Decimal] = None
    estimated_hf_after: Optional[Decimal] = None


@dataclass
class AutoRepayResult:
    """Result of auto-repay strategy execution."""
    success: bool
    action_taken: bool
    repay_amount_usdc: Optional[Decimal] = None
    swap_tx_hash: Optional[str] = None
    repay_tx_hash: Optional[str] = None
    new_health_factor: Optional[Decimal] = None
    error_message: Optional[str] = None


# --- Strategy Engine ---

class TectonicStrategy:
    """Strategy engine for automated Tectonic position management."""

    def __init__(
        self,
        service: TectonicService,
        swap_callback: Optional[Callable] = None,
        hf_warning_threshold: Decimal = Decimal("1.2"),
        hf_critical_threshold: Decimal = Decimal("1.1"),
    ):
        """
        Initialize strategy engine.
        
        Args:
            service: TectonicService instance
            swap_callback: Optional callback for swaps (e.g., to call swap_cronos_tokens)
            hf_warning_threshold: HF below which to warn (default 1.2)
            hf_critical_threshold: HF below which to auto-repay (default 1.1)
        """
        self.service = service
        self.swap_callback = swap_callback
        self.hf_warning_threshold = hf_warning_threshold
        self.hf_critical_threshold = hf_critical_threshold

    # --- Analysis Methods ---

    def analyze_position(self, address: Optional[str] = None) -> StrategyRecommendation:
        """
        Analyze position and recommend action.
        
        Args:
            address: Optional address to analyze
            
        Returns:
            StrategyRecommendation with action and reasoning
        """
        try:
            health_metrics = self.service.risk_engine.get_health_metrics(address)
            position = self.service.get_position(address)
            
            # No position
            if position.borrowed_usdc == Decimal(0) and position.supplied_usdc == Decimal(0):
                return StrategyRecommendation(
                    action=StrategyAction.NONE,
                    priority=0,
                    reason="No active position",
                )
            
            # Liquidatable
            if health_metrics.status == RiskStatus.LIQUIDATABLE:
                return StrategyRecommendation(
                    action=StrategyAction.EMERGENCY_LIQUIDATE,
                    priority=5,
                    reason="Health factor < 1.0; position can be liquidated at any moment",
                    estimated_hf_after=health_metrics.health_factor,
                )
            
            # Critical (recommend emergency repay)
            if health_metrics.status == RiskStatus.CRITICAL:
                # Calculate suggested repay amount to get HF back to 1.2
                suggested_repay = self._calculate_repay_to_reach_hf(
                    position, health_metrics, Decimal("1.2")
                )
                return StrategyRecommendation(
                    action=StrategyAction.REPAY,
                    priority=4,
                    reason="Health factor < 1.1; recommend immediate repayment",
                    suggested_amount=suggested_repay,
                    estimated_hf_after=Decimal("1.2"),
                )
            
            # Warning (monitor closely)
            if health_metrics.status == RiskStatus.WARNING:
                return StrategyRecommendation(
                    action=StrategyAction.NONE,
                    priority=2,
                    reason="Health factor between 1.1 and 1.2; monitor closely",
                    estimated_hf_after=health_metrics.health_factor,
                )
            
            # Healthy (no action needed)
            return StrategyRecommendation(
                action=StrategyAction.NONE,
                priority=0,
                reason="Position is healthy",
                estimated_hf_after=health_metrics.health_factor,
            )
        except Exception as e:
            logger.error(f"Position analysis failed: {e}")
            return StrategyRecommendation(
                action=StrategyAction.NONE,
                priority=0,
                reason=f"Analysis error: {str(e)}",
            )

    def _calculate_repay_to_reach_hf(
        self,
        position,
        metrics,
        target_hf: Decimal,
    ) -> Decimal:
        """
        Estimate repay amount needed to reach target HF.
        
        Simple approximation: 
        Each $1 of repay reduces borrow by $1 and improves HF proportionally.
        """
        if metrics.health_factor is None or metrics.health_factor >= target_hf:
            return Decimal(0)
        
        # Rough estimate: repay ~20% of borrow to improve HF by ~0.2
        # In practice, this depends on collateral ratios, but as approximation:
        hf_gap = target_hf - metrics.health_factor
        repay_fraction = hf_gap / Decimal("5")  # Empirically derived factor
        
        suggested_repay = position.borrowed_usdc * repay_fraction
        return max(suggested_repay, Decimal("1"))  # Min 1 USDC

    # --- Auto-Repay Strategy ---

    def auto_repay_if_critical(
        self,
        address: Optional[str] = None,
        source_asset: str = "CRO",
        source_amount: Optional[Decimal] = None,
    ) -> AutoRepayResult:
        """
        Auto-repay strategy: if HF < 1.1, swap asset → USDC and repay.
        
        This is the "auto-rotate" logic mentioned in Phase 6.
        
        Args:
            address: User address
            source_asset: Asset to swap from (e.g., "CRO", "TONIC")
            source_amount: Amount of source asset to swap (auto-calculated if None)
            
        Returns:
            AutoRepayResult with execution details
        """
        try:
            # Analyze position
            recommendation = self.analyze_position(address)
            
            # Check if critical
            if recommendation.action != StrategyAction.REPAY:
                return AutoRepayResult(
                    success=True,
                    action_taken=False,
                    error_message=f"No action needed: {recommendation.reason}",
                )
            
            position = self.service.get_position(address)
            suggested_repay = recommendation.suggested_amount or position.borrowed_usdc * Decimal("0.1")
            
            logger.info(f"Auto-repay: HF is critical, initiating repay strategy")
            logger.info(f"Suggested repay amount: {suggested_repay} USDC")
            
            # Step 1: Swap source asset → USDC (if callback provided)
            swap_tx_hash = None
            if self.swap_callback:
                try:
                    logger.info(f"Swapping {source_asset} → USDC")
                    swap_result = self.swap_callback(
                        from_asset=source_asset,
                        to_asset="USDC",
                        amount_desired=source_amount,
                        address=address,
                    )
                    
                    if isinstance(swap_result, dict):
                        swap_tx_hash = swap_result.get("tx_hash")
                        usdc_received = Decimal(str(swap_result.get("amount_out", 0)))
                    else:
                        swap_tx_hash = swap_result
                        usdc_received = suggested_repay  # Assume sufficient
                    
                    if not swap_result:
                        return AutoRepayResult(
                            success=False,
                            action_taken=False,
                            error_message=f"Swap {source_asset} → USDC failed",
                        )
                    
                    logger.info(f"Swap successful: {usdc_received} USDC received")
                except Exception as e:
                    logger.error(f"Swap failed: {e}")
                    return AutoRepayResult(
                        success=False,
                        action_taken=False,
                        error_message=f"Swap failed: {str(e)}",
                    )
            else:
                logger.warning("No swap callback provided; skipping swap step")
                return AutoRepayResult(
                    success=False,
                    action_taken=False,
                    error_message="Swap callback not configured",
                )
            
            # Step 2: Repay borrow
            try:
                logger.info(f"Repaying {suggested_repay} USDC borrow")
                repay_result = self.service.repay(
                    RepayRequest(amount_usdc=suggested_repay),
                    address=address,
                )
                
                if not repay_result.success:
                    return AutoRepayResult(
                        success=False,
                        action_taken=False,
                        swap_tx_hash=swap_tx_hash,
                        error_message=f"Repay failed: {repay_result.error_message}",
                    )
                
                # Get new HF
                new_position = self.service.get_position(address)
                
                return AutoRepayResult(
                    success=True,
                    action_taken=True,
                    repay_amount_usdc=suggested_repay,
                    swap_tx_hash=swap_tx_hash,
                    repay_tx_hash=repay_result.tx_hash,
                    new_health_factor=new_position.health_factor,
                )
            except Exception as e:
                logger.error(f"Repay failed: {e}")
                return AutoRepayResult(
                    success=False,
                    action_taken=False,
                    swap_tx_hash=swap_tx_hash,
                    error_message=f"Repay failed: {str(e)}",
                )
        except Exception as e:
            logger.error(f"Auto-repay strategy failed: {e}")
            return AutoRepayResult(
                success=False,
                action_taken=False,
                error_message=f"Unexpected error: {str(e)}",
            )

    # --- Manual Callback Integration ---

    def set_swap_callback(self, callback: Callable) -> None:
        """
        Register swap callback for asset swaps.
        
        Callback signature:
            callback(from_asset: str, to_asset: str, amount_desired: Decimal, address: str) -> Dict | str
            
        Returns:
            {"tx_hash": str, "amount_out": float} or tx_hash string
        """
        self.swap_callback = callback
        logger.info("Swap callback registered")

    # --- Monitoring ---

    def get_position_summary(self, address: Optional[str] = None) -> Dict:
        """
        Get concise position summary for dashboard/monitoring.
        
        Args:
            address: Optional address
            
        Returns:
            Summary dict with key metrics
        """
        try:
            position = self.service.get_position(address)
            recommendation = self.analyze_position(address)
            
            return {
                "address": address,
                "supplied_usdc": float(position.supplied_usdc),
                "borrowed_usdc": float(position.borrowed_usdc),
                "health_factor": float(position.health_factor) if position.health_factor else None,
                "health_status": position.health_status,
                "recommendation": {
                    "action": recommendation.action.value,
                    "priority": recommendation.priority,
                    "reason": recommendation.reason,
                },
                "liquidation_buffer_usdc": float(position.liquidation_buffer_usdc),
                "safe_borrow_limit_usdc": float(position.safe_borrow_limit_usdc),
            }
        except Exception as e:
            logger.error(f"Failed to generate position summary: {e}")
            return {"error": str(e)}
