#!/usr/bin/env python3
"""
Phase 5: Infrastructure demo - Provider Manager and Gas Strategy.

Demonstrates:
- RPC provider failover
- EIP-1559 gas calculation
- Gas summary reporting

Usage:
    python -m app.defi.tectonic.infrastructure_demo
"""

import sys

from .gas import create_gas_strategy
from .providers import create_provider_manager


def main() -> None:
    """Demo the Phase 5 infrastructure components."""
    print("=" * 60)
    print("PHASE 5: INFRASTRUCTURE DEMO")
    print("=" * 60)

    # 1) Provider Manager
    print("\n1) Testing Provider Manager (RPC Failover)...")
    print("-" * 60)
    try:
        provider_manager = create_provider_manager()
        web3 = provider_manager.get_web3()

        print(f"Connected to: {web3.provider.endpoint_uri if hasattr(web3.provider, 'endpoint_uri') else 'unknown'}")
        print(f"Chain ID: {web3.eth.chain_id}")
        print(f"Latest block: {web3.eth.block_number}")

        # Show status of all endpoints
        print("\nEndpoint status:")
        status = provider_manager.get_status()
        for url, info in status.items():
            health = "[OK]" if info["healthy"] else "[FAIL]"
            print(f"  {health} {url}")
            if info["last_error"]:
                print(f"      Last error: {info['last_error']}")

    except Exception as e:
        print(f"[ERROR] Provider manager failed: {e}")
        sys.exit(1)

    # 2) Gas Strategy
    print("\n2) Testing Gas Strategy (EIP-1559)...")
    print("-" * 60)
    try:
        gas_strategy = create_gas_strategy(web3)

        # Get gas summary
        summary = gas_strategy.get_gas_summary()
        if "error" in summary:
            print(f"[ERROR] Gas strategy error: {summary['error']}")
        else:
            print("Current gas conditions:")
            print(f"  Base Fee: {summary['base_fee_gwei']:.4f} gwei ({summary['base_fee_wei']} wei)")
            print(f"  Priority Fee: {summary['priority_fee_gwei']:.4f} gwei ({summary['priority_fee_wei']} wei)")
            print(f"  Max Fee Per Gas: {summary['max_fee_per_gas_gwei']:.4f} gwei ({summary['max_fee_per_gas_wei']} wei)")
            print(f"  Base Fee Multiplier: {summary['base_fee_multiplier']}x")

        # Calculate gas params
        gas_params = gas_strategy.calculate_gas_params(gas_limit=200000)
        print(f"\nExample transaction gas params:")
        print(f"  Gas Limit: {gas_params.gas_limit}")
        print(f"  Max Fee Per Gas: {gas_params.max_fee_per_gas} wei ({web3.from_wei(gas_params.max_fee_per_gas, 'gwei'):.4f} gwei)")
        print(f"  Max Priority Fee Per Gas: {gas_params.max_priority_fee_per_gas} wei ({web3.from_wei(gas_params.max_priority_fee_per_gas, 'gwei'):.4f} gwei)")

        # Estimate total cost
        total_cost_wei = gas_params.max_fee_per_gas * gas_params.gas_limit
        total_cost_gwei = web3.from_wei(total_cost_wei, "gwei")
        print(f"  Estimated Total Cost: {total_cost_wei} wei ({total_cost_gwei:.4f} gwei)")

    except Exception as e:
        print(f"[ERROR] Gas strategy failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 60)
    print("[OK] Infrastructure demo completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()

