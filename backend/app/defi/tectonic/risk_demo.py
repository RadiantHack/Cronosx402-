#!/usr/bin/env python3
"""
Phase 4: Risk Engine demo script.

Demonstrates:
- Health Factor calculation
- Safe borrow limit computation
- Threshold-based status monitoring
- Position health checks

Usage:
    python -m app.defi.tectonic.risk_demo [--private-key 0x...]
"""

import argparse
import os
import sys
from decimal import Decimal

from dotenv import load_dotenv

from .client import TectonicClient, TectonicError
from .risk_engine import RiskEngine, RiskStatus, HealthMetrics

load_dotenv()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demonstrate Tectonic Risk Engine health monitoring.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--private-key",
        dest="private_key",
        type=str,
        default=None,
        help="Hex private key for the wallet (or set TECTONIC_PRIVATE_KEY env var).",
    )
    parser.add_argument(
        "--safety-ltv",
        type=float,
        default=0.75,
        help="Safety LTV ratio (0.0-1.0). Default: 0.75 (75%% of available liquidity).",
    )
    return parser.parse_args()


def _get_private_key(cli_private_key: str | None) -> str:
    pk = cli_private_key or os.getenv("TECTONIC_PRIVATE_KEY")
    if not pk:
        raise TectonicError("Private key is required. Use --private-key or set TECTONIC_PRIVATE_KEY.")
    if not pk.startswith("0x"):
        pk = "0x" + pk
    return pk


def _print_health_metrics(metrics: HealthMetrics) -> None:
    """Pretty-print health metrics."""
    print("\n" + "=" * 60)
    print("TECTONIC POSITION HEALTH REPORT")
    print("=" * 60)

    # Status with ASCII-safe indicators
    status_indicator = {
        RiskStatus.HEALTHY: "[OK]",
        RiskStatus.WARNING: "[WARN]",
        RiskStatus.CRITICAL: "[CRITICAL]",
        RiskStatus.LIQUIDATABLE: "[LIQUIDATABLE]",
    }
    indicator = status_indicator.get(metrics.status, "[?]")

    print(f"\nStatus: {indicator} {metrics.status.value.upper()}")

    if metrics.health_factor < Decimal("999"):
        print(f"Health Factor (HF): {metrics.health_factor:.4f}")
        if metrics.health_factor < Decimal("1.0"):
            print("  [WARN] Position is LIQUIDATABLE!")
        elif metrics.health_factor < Decimal("1.1"):
            print("  [WARN] Position is CRITICAL - immediate action recommended")
        elif metrics.health_factor < Decimal("1.2"):
            print("  [WARN] Position is in WARNING zone - monitor closely")
        else:
            print("  [OK] Position is healthy")
    else:
        print("Health Factor: N/A (no borrows)")

    print(f"\nCollateral:")
    print(f"  Total Collateral Value: ${metrics.total_collateral_usd:.2f} USD")

    print(f"\nBorrows:")
    print(f"  Total Borrow Value: ${metrics.total_borrow_usd:.2f} USD")
    if metrics.shortfall_usd > Decimal("0"):
        print(f"  [WARN] Shortfall: ${metrics.shortfall_usd:.2f} USD (position is underwater)")

    print(f"\nBorrow Limits:")
    print(f"  Available Liquidity: ${metrics.available_liquidity_usd:.2f} USD")
    print(f"  Max Borrow Limit (100%%): ${metrics.max_borrow_limit_usd:.2f} USD")
    print(f"  Safe Borrow Limit (with buffer): ${metrics.safe_borrow_limit_usd:.2f} USD")

    print("\n" + "=" * 60)


def _test_safe_borrow_check(engine: RiskEngine, test_amount_usd: Decimal) -> None:
    """Test if a borrow amount would be safe."""
    test_amount_wei = int(test_amount_usd * Decimal(10**6))  # USDC has 6 decimals
    is_safe, reason = engine.can_borrow_safely(test_amount_wei)

    print(f"\n--- Safe Borrow Check ---")
    print(f"Test borrow amount: ${test_amount_usd:.2f} USD")
    if is_safe:
        print(f"[OK] SAFE: {reason}")
    else:
        print(f"[FAIL] NOT SAFE: {reason}")


def main() -> None:
    args = _parse_args()

    try:
        private_key = _get_private_key(args.private_key)
        client = TectonicClient(private_key=private_key)
        print(f"Connected to Cronos mainnet via {client.rpc_url}")
        print(f"Monitoring account: {client.address}")

        # Initialize risk engine with safety LTV
        safety_ltv = Decimal(str(args.safety_ltv))
        if not (Decimal("0") < safety_ltv <= Decimal("1")):
            print("Error: --safety-ltv must be between 0.0 and 1.0")
            sys.exit(1)

        engine = RiskEngine(client, safety_ltv=safety_ltv)
        print(f"Risk Engine initialized with safety LTV: {safety_ltv * 100:.0f}%")

        # Get current health metrics
        metrics = engine.get_health_metrics()
        _print_health_metrics(metrics)

        # Get safe borrow limit
        safe_limit_wei, safe_limit_usd = engine.get_safe_borrow_limit()
        print(f"\n--- Safe Borrow Limit ---")
        print(f"Safe borrow limit: {safe_limit_wei} wei (${safe_limit_usd:.2f} USD)")

        # Test a few borrow amounts
        if safe_limit_usd > Decimal("0"):
            # Test 50% of safe limit
            test_50pct = safe_limit_usd * Decimal("0.5")
            _test_safe_borrow_check(engine, test_50pct)

            # Test 100% of safe limit
            _test_safe_borrow_check(engine, safe_limit_usd)

            # Test 120% of safe limit (should fail)
            test_120pct = safe_limit_usd * Decimal("1.2")
            _test_safe_borrow_check(engine, test_120pct)

        # Monitor position (with callback example)
        print(f"\n--- Position Monitoring ---")
        print("Running position health check...")

        def health_callback(m: HealthMetrics) -> None:
            """Example callback for health monitoring."""
            if m.status in (RiskStatus.CRITICAL, RiskStatus.LIQUIDATABLE):
                print(f"  [ALERT] Position status changed to {m.status.value}")

        monitored_metrics = engine.monitor_position(callback=health_callback)
        print("Monitoring complete.")

        print("\n[OK] Risk Engine demo finished.")

    except TectonicError as exc:
        print(f"\n[ERROR] Tectonic error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Unexpected error: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

