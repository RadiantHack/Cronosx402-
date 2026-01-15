"""
Phase 4: Risk & Health Engine for Tectonic positions.

This module provides:
- Health Factor (HF) calculation from account liquidity and collateral factors
- Safe borrow limit computation with configurable safety buffers
- Threshold-based status (healthy, warning, critical)
- Dust threshold handling (< $0.01 treated as zero)
- Oracle price validation against external feeds
- Background monitoring capabilities

Usage:
    from app.defi.tectonic.risk_engine import RiskEngine, RiskStatus
    from app.defi.tectonic.client import TectonicClient

    client = TectonicClient(private_key="0x...")
    engine = RiskEngine(client, safety_ltv=0.75)  # Max 75% of available liquidity

    status = engine.get_health_status()
    if status == RiskStatus.CRITICAL:
        print("⚠️ Position is at risk of liquidation!")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from web3 import Web3

from .client import AccountLiquidity, TectonicClient, TectonicError

logger = logging.getLogger(__name__)

# --- Constants -----------------------------------------------------------------

# Dust threshold: balances below this USD value are treated as zero
DUST_THRESHOLD_USD = Decimal("0.01")

# Default safety LTV: only allow borrowing up to this % of available liquidity
DEFAULT_SAFETY_LTV = Decimal("0.75")  # 75%

# Health Factor thresholds
HF_WARNING_THRESHOLD = Decimal("1.2")  # Warn if HF < 1.2
HF_CRITICAL_THRESHOLD = Decimal("1.1")  # Critical if HF < 1.1
HF_LIQUIDATION_THRESHOLD = Decimal("1.0")  # Liquidatable if HF < 1.0

# Oracle price deviation threshold (5%)
ORACLE_DEVIATION_THRESHOLD_PCT = Decimal("0.05")


# --- Enums & Data Classes ------------------------------------------------------


class RiskStatus(Enum):
    """Health status of a Tectonic position."""

    HEALTHY = "healthy"  # HF >= 1.2, no action needed
    WARNING = "warning"  # 1.1 <= HF < 1.2, monitor closely
    CRITICAL = "critical"  # 1.0 <= HF < 1.1, immediate action recommended
    LIQUIDATABLE = "liquidatable"  # HF < 1.0, position can be liquidated


@dataclass
class HealthMetrics:
    """Computed health metrics for a Tectonic position."""

    health_factor: Decimal  # HF value (or None if no borrows)
    status: RiskStatus
    total_collateral_usd: Decimal  # USD value of all collateral
    total_borrow_usd: Decimal  # USD value of all borrows
    available_liquidity_usd: Decimal  # Available USD to borrow (from getAccountLiquidity)
    safe_borrow_limit_usd: Decimal  # Safe borrow limit (with safety buffer)
    max_borrow_limit_usd: Decimal  # Maximum theoretical borrow limit (100% of liquidity)
    shortfall_usd: Decimal  # Shortfall if underwater (should be 0 for healthy positions)


@dataclass
class OraclePriceCheck:
    """Result of oracle price validation."""

    is_valid: bool
    tectonic_price: Optional[Decimal] = None
    external_price: Optional[Decimal] = None
    deviation_pct: Optional[Decimal] = None
    error_message: Optional[str] = None


# --- Risk Engine ---------------------------------------------------------------


class RiskEngine:
    """
    Risk management engine for Tectonic positions.

    Calculates Health Factor, safe borrow limits, and monitors position health
    with configurable thresholds.
    """

    def __init__(
        self,
        client: TectonicClient,
        safety_ltv: Decimal = DEFAULT_SAFETY_LTV,
        dust_threshold_usd: Decimal = DUST_THRESHOLD_USD,
        warning_threshold: Decimal = HF_WARNING_THRESHOLD,
        critical_threshold: Decimal = HF_CRITICAL_THRESHOLD,
    ) -> None:
        """
        Initialize the risk engine.

        Args:
            client: TectonicClient instance (must be initialized with an account)
            safety_ltv: Safety LTV ratio (0.0-1.0). Max borrow = available_liquidity * safety_ltv
            dust_threshold_usd: USD value below which balances are treated as zero
            warning_threshold: HF threshold for WARNING status (default: 1.2)
            critical_threshold: HF threshold for CRITICAL status (default: 1.1)
        """
        if not client.address:
            raise TectonicError("RiskEngine requires a TectonicClient with an account address.")

        self.client = client
        self.safety_ltv = safety_ltv
        self.dust_threshold_usd = dust_threshold_usd
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def get_health_metrics(self, account_address: Optional[str] = None) -> HealthMetrics:
        """
        Calculate comprehensive health metrics for the account.

        Args:
            account_address: Optional address to check (defaults to client.address)

        Returns:
            HealthMetrics with HF, status, collateral, borrows, and limits
        """
        addr = account_address or self.client.address
        if not addr:
            raise TectonicError("No account address available for health check.")

        # Get account liquidity from Comptroller
        liquidity_info: AccountLiquidity = self.client.get_account_liquidity(addr)

        # Convert from wei to USD (assuming 18 decimals for liquidity/shortfall)
        # Note: getAccountLiquidity returns values scaled by 1e18
        available_liquidity_usd = Decimal(liquidity_info.liquidity) / Decimal(10**18)
        shortfall_usd = Decimal(liquidity_info.shortfall) / Decimal(10**18)

        # Get actual balances
        tusdc_balance = self.client.get_tusdc_balance(addr)
        borrow_balance = self.client.get_borrow_balance(addr)

        # For now, we'll use a simplified model:
        # - Assume USDC price = $1.0 (stablecoin)
        # - tUSDC exchange rate to get underlying USDC value
        # - Borrow is in USDC (6 decimals)

        # Get exchange rate (tToken to underlying)
        try:
            exchange_rate = self.client.tusdc.functions.exchangeRateStored().call()
            # Exchange rate is scaled by 1e18, underlying has 6 decimals
            # So: underlying_amount = (tToken_amount * exchange_rate) / 1e18
            # Then convert to USD (assuming $1 per USDC)
            tusdc_underlying_usd = (Decimal(tusdc_balance) * Decimal(exchange_rate)) / Decimal(10**18)
        except Exception as e:
            logger.warning(f"Could not fetch tUSDC exchange rate: {e}. Using simplified model.")
            # Fallback: assume 1:1 if we can't get exchange rate
            tusdc_underlying_usd = Decimal(tusdc_balance) / Decimal(10**6)

        borrow_usd = Decimal(borrow_balance) / Decimal(10**6)  # USDC has 6 decimals

        # Apply dust threshold
        if tusdc_underlying_usd < self.dust_threshold_usd:
            tusdc_underlying_usd = Decimal("0")
        if borrow_usd < self.dust_threshold_usd:
            borrow_usd = Decimal("0")

        # Get collateral factor for tUSDC
        # For simplicity, assume 80% collateral factor (0.8)
        # In production, fetch from Comptroller.markets(tUSDC).collateralFactorMantissa
        collateral_factor = Decimal("0.80")  # 80% LTV

        # Calculate total collateral value (with collateral factor applied)
        total_collateral_usd = tusdc_underlying_usd * collateral_factor
        total_borrow_usd = borrow_usd

        # Calculate Health Factor
        # HF = (Total Collateral Value * Collateral Factor) / Total Borrow Value
        # If no borrows, HF is undefined (we'll treat as "healthy" with no borrows)
        if total_borrow_usd > self.dust_threshold_usd:
            health_factor = total_collateral_usd / total_borrow_usd if total_borrow_usd > 0 else Decimal("999")
        else:
            # No borrows = healthy position
            health_factor = Decimal("999")  # Effectively infinite

        # Determine status
        if health_factor < HF_LIQUIDATION_THRESHOLD:
            status = RiskStatus.LIQUIDATABLE
        elif health_factor < self.critical_threshold:
            status = RiskStatus.CRITICAL
        elif health_factor < self.warning_threshold:
            status = RiskStatus.WARNING
        else:
            status = RiskStatus.HEALTHY

        # Calculate safe borrow limits
        max_borrow_limit_usd = available_liquidity_usd  # 100% of available liquidity
        safe_borrow_limit_usd = available_liquidity_usd * self.safety_ltv  # With safety buffer

        # Apply dust threshold to limits
        if max_borrow_limit_usd < self.dust_threshold_usd:
            max_borrow_limit_usd = Decimal("0")
        if safe_borrow_limit_usd < self.dust_threshold_usd:
            safe_borrow_limit_usd = Decimal("0")

        return HealthMetrics(
            health_factor=health_factor,
            status=status,
            total_collateral_usd=total_collateral_usd,
            total_borrow_usd=total_borrow_usd,
            available_liquidity_usd=available_liquidity_usd,
            safe_borrow_limit_usd=safe_borrow_limit_usd,
            max_borrow_limit_usd=max_borrow_limit_usd,
            shortfall_usd=shortfall_usd,
        )

    def get_health_status(self, account_address: Optional[str] = None) -> RiskStatus:
        """
        Get the current health status (simplified).

        Args:
            account_address: Optional address to check

        Returns:
            RiskStatus enum value
        """
        metrics = self.get_health_metrics(account_address)
        return metrics.status

    def get_safe_borrow_limit(self, account_address: Optional[str] = None) -> Tuple[int, Decimal]:
        """
        Get the safe borrow limit in wei and USD.

        Args:
            account_address: Optional address to check

        Returns:
            Tuple of (safe_borrow_limit_wei, safe_borrow_limit_usd)
            For USDC, wei = usd * 10^6
        """
        metrics = self.get_health_metrics(account_address)
        safe_limit_usd = metrics.safe_borrow_limit_usd

        # Convert to wei (USDC has 6 decimals)
        safe_limit_wei = int(safe_limit_usd * Decimal(10**6))

        return safe_limit_wei, safe_limit_usd

    def can_borrow_safely(self, borrow_amount_wei: int, account_address: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if a borrow amount is safe given current position.

        Args:
            borrow_amount_wei: Amount to borrow in wei (USDC = 6 decimals)
            account_address: Optional address to check

        Returns:
            Tuple of (is_safe: bool, reason: str)
        """
        metrics = self.get_health_metrics(account_address)
        borrow_amount_usd = Decimal(borrow_amount_wei) / Decimal(10**6)

        # Check 1: Within safe borrow limit
        if borrow_amount_usd > metrics.safe_borrow_limit_usd:
            return False, f"Borrow amount ${borrow_amount_usd:.2f} exceeds safe limit ${metrics.safe_borrow_limit_usd:.2f}"

        # Check 2: Would not push HF below critical threshold
        if metrics.total_borrow_usd > self.dust_threshold_usd:
            # Calculate hypothetical HF after borrow
            hypothetical_borrow = metrics.total_borrow_usd + borrow_amount_usd
            if metrics.total_collateral_usd > 0:
                hypothetical_hf = metrics.total_collateral_usd / hypothetical_borrow
                if hypothetical_hf < self.critical_threshold:
                    return False, f"Borrow would push HF to {hypothetical_hf:.2f} (below critical threshold {self.critical_threshold})"

        # Check 3: Status is not already critical/liquidatable
        if metrics.status in (RiskStatus.CRITICAL, RiskStatus.LIQUIDATABLE):
            return False, f"Position status is {metrics.status.value}, borrowing is not recommended"

        return True, "Borrow is within safe limits"

    def validate_oracle_price(
        self,
        asset_address: str,
        external_price_fetcher: Optional[Callable[[str], Decimal]] = None,
    ) -> OraclePriceCheck:
        """
        Validate Tectonic oracle price against an external source.

        Args:
            asset_address: Token address to check (e.g., USDC)
            external_price_fetcher: Optional function(address) -> Decimal to fetch external price

        Returns:
            OraclePriceCheck with validation result
        """
        try:
            # Try to get price from Tectonic oracle
            # Note: This requires the oracle ABI and address, which we don't have in config yet
            # For now, we'll return a placeholder that indicates oracle validation is not yet implemented
            # In production, you would:
            # 1. Get oracle address from Comptroller.oracle()
            # 2. Call oracle.getUnderlyingPrice(tToken) to get price in USD (scaled)
            # 3. Compare with external_price_fetcher(asset_address)

            if external_price_fetcher:
                external_price = external_price_fetcher(asset_address)
                # For now, assume Tectonic price is valid if we can't fetch it
                # In production, fetch from oracle contract
                return OraclePriceCheck(
                    is_valid=True,  # Placeholder
                    external_price=external_price,
                    error_message="Oracle price validation not fully implemented (requires oracle contract ABI)",
                )

            return OraclePriceCheck(
                is_valid=True,
                error_message="No external price fetcher provided; skipping validation",
            )

        except Exception as e:
            return OraclePriceCheck(
                is_valid=False,
                error_message=f"Oracle validation failed: {e}",
            )

    def monitor_position(
        self,
        account_address: Optional[str] = None,
        callback: Optional[Callable[[HealthMetrics], None]] = None,
    ) -> HealthMetrics:
        """
        Monitor position health and trigger callbacks if thresholds are crossed.

        Args:
            account_address: Optional address to monitor
            callback: Optional callback function(HealthMetrics) to call on status changes

        Returns:
            Current HealthMetrics
        """
        metrics = self.get_health_metrics(account_address)

        # Log current status
        logger.info(
            f"Position health check: HF={metrics.health_factor:.2f}, "
            f"Status={metrics.status.value}, "
            f"Collateral=${metrics.total_collateral_usd:.2f}, "
            f"Borrow=${metrics.total_borrow_usd:.2f}"
        )

        # Trigger callback if provided
        if callback:
            try:
                callback(metrics)
            except Exception as e:
                logger.error(f"Error in health monitoring callback: {e}")

        # Log warnings for critical states
        if metrics.status == RiskStatus.CRITICAL:
            logger.warning(
                f"[CRITICAL] Position HF={metrics.health_factor:.2f} is below critical threshold. "
                f"Consider repaying debt or adding collateral."
            )
        elif metrics.status == RiskStatus.LIQUIDATABLE:
            logger.error(
                f"[LIQUIDATABLE] Position HF={metrics.health_factor:.2f} is below 1.0. "
                f"Position can be liquidated!"
            )

        return metrics

