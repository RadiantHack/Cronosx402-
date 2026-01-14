#!/usr/bin/env python3
"""
Phase 3: Tectonic workflow demo script.

Runs a small, production-style flow on Cronos mainnet using TectonicClient:
- Supply USDC -> tUSDC
- Enter tUSDC as collateral (if not already)
- Borrow USDC
- (Optionally) Repay and Redeem

Intended for:
- Manual verification with a funded test wallet
- Integration testing hooks later
"""

import os
import sys
import argparse
from decimal import Decimal

from dotenv import load_dotenv

from .client import TectonicClient, TectonicError, AccountLiquidity

# Load environment variables from backend/.env if present so TECTONIC_PRIVATE_KEY
# can be configured there as well as via the shell.
load_dotenv()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a simple Tectonic USDC workflow on Cronos mainnet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--private-key",
        dest="private_key",
        type=str,
        default=None,
        help="Hex private key for the test wallet (or set TECTONIC_PRIVATE_KEY env var).",
    )
    parser.add_argument(
        "--supply",
        type=float,
        default=10.0,
        help="USDC amount to supply as collateral (default: 10.0).",
    )
    parser.add_argument(
        "--borrow",
        type=float,
        default=5.0,
        help="USDC amount to borrow (default: 5.0).",
    )
    parser.add_argument(
        "--skip-repay",
        action="store_true",
        help="If set, will not repay or redeem, leaving the position open.",
    )
    return parser.parse_args()


def _get_private_key(cli_private_key: str | None) -> str:
    pk = cli_private_key or os.getenv("TECTONIC_PRIVATE_KEY")
    if not pk:
        raise TectonicError("Private key is required. Use --private-key or set TECTONIC_PRIVATE_KEY.")
    if not pk.startswith("0x"):
        pk = "0x" + pk
    return pk


def _to_wei(amount: float, decimals: int = 6) -> int:
    return int(Decimal(str(amount)) * (10 ** decimals))


def _print_liquidity(client: TectonicClient) -> None:
    info: AccountLiquidity = client.get_account_liquidity()
    print(
        f"AccountLiquidity -> error={info.error}, liquidity={info.liquidity}, shortfall={info.shortfall}"
    )


def main() -> None:
    args = _parse_args()

    try:
        private_key = _get_private_key(args.private_key)
        client = TectonicClient(private_key=private_key)
        print(f"Connected to Cronos mainnet via {client.rpc_url}")
        print(f"Using account: {client.address}")

        # Convert amounts to smallest units (USDC has 6 decimals)
        supply_amount_wei = _to_wei(args.supply, decimals=6)
        borrow_amount_wei = _to_wei(args.borrow, decimals=6)

        print("\n== Initial balances ==")
        print(f"USDC:  {client.get_usdc_balance()} (wei)")
        print(f"tUSDC: {client.get_tusdc_balance()} (tTokens)")
        _print_liquidity(client)

        # 1) Supply USDC
        print(f"\n== Supplying {args.supply} USDC to Tectonic ==")
        client.supply_usdc(supply_amount_wei)
        print("Supply complete.")
        print(f"New tUSDC balance: {client.get_tusdc_balance()} (tTokens)")

        # 2) Enter market if needed
        print("\n== Ensuring tUSDC is enabled as collateral ==")
        client.enter_markets_if_needed()
        print("Collateral status ensured.")

        _print_liquidity(client)

        # 3) Borrow USDC
        print(f"\n== Borrowing {args.borrow} USDC from Tectonic ==")
        client.borrow_usdc(borrow_amount_wei)
        print("Borrow complete.")
        print(f"Borrow balance (USDC): {client.get_borrow_balance()} (wei)")
        _print_liquidity(client)

        if args.skip_repay:
            print("\nSkip-repay flag set; leaving position open.")
            sys.exit(0)

        # 4) Repay USDC
        print(f"\n== Repaying {args.borrow} USDC ==")
        client.repay_usdc(borrow_amount_wei)
        print("Repay transaction sent.")
        print(f"Borrow balance after repay: {client.get_borrow_balance()} (wei)")
        _print_liquidity(client)

        # 5) Redeem supplied collateral
        print(f"\n== Redeeming supplied collateral ({args.supply} USDC) ==")
        client.redeem_usdc(supply_amount_wei)
        print("Redeem complete.")
        print(f"Final USDC balance:  {client.get_usdc_balance()} (wei)")
        print(f"Final tUSDC balance: {client.get_tusdc_balance()} (tTokens)")
        _print_liquidity(client)

        print("\n✅ Workflow finished.")

    except TectonicError as exc:
        print(f"\n❌ Tectonic error: {exc}")
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - top-level safety
        print(f"\n❌ Unexpected error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()


