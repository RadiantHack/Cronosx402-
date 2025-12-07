#!/usr/bin/env python3
"""
Script to get balance on Movement blockchain using the Cronos Indexer API.

This script uses the Cronos Indexer GraphQL API to retrieve balances
for a given wallet address. It supports all fungible asset balances including
native MOV token and ERC-20 tokens.

Reference: https://docs.movementnetwork.xyz/devs/indexing#defi-queries

Usage:
    python get_movement_balance.py <address> [--network NETWORK] [--indexer-url URL]
    
Examples:
    # Get all token balances on mainnet
    python get_movement_balance.py 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
    
    # Get all token balances on testnet
    python get_movement_balance.py 0x02d969ad6f7cca2c08226eda6ad8971ca99357ba9f192faed1c4186200b789fa --network testnet
    
    # Get balances with custom indexer URL
    python3 get_movement_balance.py 0x02d969ad6f7cca2c08226eda6ad8971ca99357ba9f192faed1c4186200b789fa --indexer-url https://indexer.mainnet.movementnetwork.xyz/v1/graphql
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    print(
        "Error: 'requests' module not found. Please install dependencies:\n"
        "  python3 -m venv venv\n"
        "  source venv/bin/activate\n"
        "  pip install -e .\n"
        "Or install requests directly:\n"
        "  pip install requests"
    )
    sys.exit(1)

# Constants
DEFAULT_NETWORK = "mainnet"
DEFAULT_INDEXER_MAINNET = "https://indexer.mainnet.movementnetwork.xyz/v1/graphql"
DEFAULT_INDEXER_TESTNET = "https://indexer.testnet.movementnetwork.xyz/v1/graphql"
# Third-party indexer (Sentio) - may be more accessible
SENTIO_INDEXER = "https://rpc.sentio.xyz/movement-indexer/v1/graphql"
ENV_INDEXER_URL = "CRONOS_INDEXER_URL"
ENV_NETWORK = "CRONOS_NETWORK"

# GraphQL query to get user token balances
GET_USER_BALANCES_QUERY = """
query GetUserTokenBalances($ownerAddress: String!) {
  current_fungible_asset_balances(
    where: {
      owner_address: {_eq: $ownerAddress},
      amount: {_gt: 0}
    }
  ) {
    asset_type
    amount
    last_transaction_timestamp
    metadata {
      name
      symbol
      decimals
    }
  }
}
"""


def get_indexer_url(network: str, custom_url: Optional[str] = None) -> str:
    """Get Cronos Indexer URL from environment, custom URL, or default.
    
    Args:
        network: Network name (mainnet or testnet)
        custom_url: Optional custom indexer URL
        
    Returns:
        Cronos Indexer GraphQL URL
    """
    if custom_url:
        return custom_url
    env_url = os.getenv(ENV_INDEXER_URL)
    if env_url:
        return env_url
    if network == "testnet":
        return DEFAULT_INDEXER_TESTNET
    return DEFAULT_INDEXER_MAINNET


def validate_address(address: str) -> bool:
    """Validate Ethereum/Movement address format.
    
    Args:
        address: Address to validate
        
    Returns:
        True if address is valid, False otherwise
    """
    if not address.startswith("0x"):
        return False
    if len(address) < 3:
        return False
    hex_part = address[2:]
    if not all(c in "0123456789abcdefABCDEF" for c in hex_part):
        return False
    return True


def format_balance(amount: str, decimals: int = 18) -> str:
    """Format balance from string amount to human-readable format.
    
    Args:
        amount: Balance as string (from GraphQL response)
        decimals: Number of decimals (default: 18)
        
    Returns:
        Formatted balance string
    """
    try:
        amount_int = int(amount)
        balance = amount_int / (10 ** decimals)
        return f"{balance:.6f}"
    except (ValueError, TypeError):
        return amount


def parse_metadata(metadata: Optional[Dict]) -> Dict[str, str]:
    """Parse metadata from GraphQL response.
    
    Args:
        metadata: Metadata dictionary from GraphQL response
        
    Returns:
        Dictionary with parsed metadata fields
    """
    if not metadata:
        return {}
    result = {}
    if isinstance(metadata, dict):
        result["name"] = metadata.get("name", "Unknown")
        result["symbol"] = metadata.get("symbol", "Unknown")
        result["decimals"] = metadata.get("decimals", "18")
    return result


def get_balances(indexer_url: str, address: str) -> Dict:
    """Get all token balances for an address using Cronos Indexer API.
    
    Args:
        indexer_url: Cronos Indexer GraphQL endpoint URL
        address: Wallet address to check
        
    Returns:
        Dictionary with balance information
    """
    try:
        variables = {"ownerAddress": address}
        payload = {
            "query": GET_USER_BALANCES_QUERY,
            "variables": variables,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = requests.post(
            indexer_url,
            json=payload,
            headers=headers,
            timeout=30,
        )
        if response.status_code == 403:
            error_detail = "Forbidden - The indexer endpoint may require authentication or have access restrictions."
            try:
                error_data = response.json()
                if "errors" in error_data:
                    error_detail += f" Details: {json.dumps(error_data['errors'])}"
            except:
                error_detail += f" Response: {response.text[:200]}"
            return {
                "address": address,
                "error": error_detail,
                "success": False,
            }
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            return {
                "address": address,
                "error": f"GraphQL errors: {json.dumps(data['errors'])}",
                "success": False,
            }
        balances = data.get("data", {}).get("current_fungible_asset_balances", [])
        return {
            "address": address,
            "balances": balances,
            "success": True,
        }
    except requests.exceptions.RequestException as e:
        return {
            "address": address,
            "error": f"Request error: {str(e)}",
            "success": False,
        }
    except Exception as e:
        return {
            "address": address,
            "error": str(e),
            "success": False,
        }


def print_balance_result(result: Dict) -> None:
    """Print balance result in a formatted way.
    
    Args:
        result: Dictionary with balance information
    """
    if not result.get("success", False):
        print(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)
    balances = result.get("balances", [])
    if not balances:
        print(f"Address: {result['address']}")
        print("No balances found (all balances are 0)")
        return
    print(f"Address: {result['address']}")
    print(f"Found {len(balances)} token balance(s):\n")
    for idx, balance in enumerate(balances, 1):
        asset_type = balance.get("asset_type", "Unknown")
        amount = balance.get("amount", "0")
        metadata = balance.get("metadata", {})
        parsed_metadata = parse_metadata(metadata)
        decimals = int(parsed_metadata.get("decimals", 18))
        symbol = parsed_metadata.get("symbol", "Unknown")
        name = parsed_metadata.get("name", "Unknown")
        formatted_balance = format_balance(amount, decimals)
        last_tx_timestamp = balance.get("last_transaction_timestamp")
        print(f"{idx}. {name} ({symbol})")
        print(f"   Asset Type: {asset_type}")
        print(f"   Balance: {formatted_balance} {symbol}")
        print(f"   Amount (raw): {amount}")
        if last_tx_timestamp:
            print(f"   Last Transaction: {last_tx_timestamp}")
        print()


def main() -> None:
    """Main function to get balance on Movement blockchain."""
    parser = argparse.ArgumentParser(
        description="Get balance on Movement blockchain using Indexer API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "address",
        type=str,
        help="Wallet address to check (0x format)",
    )
    parser.add_argument(
        "--network",
        type=str,
        choices=["mainnet", "testnet"],
        default=None,
        help=f"Network to use (default: {DEFAULT_NETWORK} or from {ENV_NETWORK})",
    )
    parser.add_argument(
        "--indexer-url",
        type=str,
        default=None,
        help="Custom Cronos Indexer GraphQL URL (overrides network setting)",
    )
    parser.add_argument(
        "--use-sentio",
        action="store_true",
        help="Use Sentio third-party indexer (may be more accessible)",
    )
    args = parser.parse_args()
    if not validate_address(args.address):
        print(f"Error: Invalid address format: {args.address}")
        print("Address must start with 0x and contain valid hexadecimal characters")
        sys.exit(1)
    network = args.network or os.getenv(ENV_NETWORK, DEFAULT_NETWORK)
    if args.use_sentio:
        indexer_url = SENTIO_INDEXER
    else:
        indexer_url = get_indexer_url(network, args.indexer_url)
    print(f"Using Cronos Indexer: {indexer_url}")
    print(f"Network: {network}")
    print()
    result = get_balances(indexer_url, args.address)
    print_balance_result(result)


if __name__ == "__main__":
    main()
