#!/usr/bin/env python3
"""
Script to get balance on Cronos blockchain using Bitquery API.

This script uses Bitquery's GraphQL API to retrieve balances for a given wallet
address on Cronos. It supports all fungible asset balances including native CRO
token and ERC-20 tokens.

Reference: https://docs.bitquery.io/v1/docs/Schema/Cronos/overview

Usage:
    python get_cronos_balance.py <address> [--network NETWORK] [--api-key KEY]
    
Examples:
    # Get all token balances on mainnet (requires BITQUERY_API_KEY env var)
    python get_cronos_balance.py 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
    
    # Get all token balances with API key
    python get_cronos_balance.py 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb --api-key YOUR_API_KEY
    
    # Get balances on testnet
    python get_cronos_balance.py 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb --network testnet
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
ENV_API_KEY = "BITQUERY_API_KEY"
ENV_NETWORK = "CRONOS_NETWORK"

# Bitquery API endpoints
BITQUERY_API_V1_URL = "https://graphql.bitquery.io"
BITQUERY_API_V2_URL = "https://graphql.bitquery.io/v2"

# GraphQL query to get user token balances using Bitquery API v2
# This query fetches native CRO balance and all token balances for an address on Cronos
GET_USER_BALANCES_QUERY = """
query GetCronosBalances($address: String!) {
  ethereum(network: cronos) {
    address(address: {is: $address}) {
      # Native coin balance (CRO)
      balance
      # Token balances (CRC-20)
      balances {
        currency {
          name
          symbol
          decimals
          address
        }
        value
      }
    }
  }
}
"""


def get_api_key(api_key: Optional[str] = None) -> str:
    """Get Bitquery API key from argument, environment, or raise error.
    
    Args:
        api_key: Optional API key from command line argument
        
    Returns:
        Bitquery API key
        
    Raises:
        SystemExit: If no API key is found
    """
    if api_key:
        return api_key
    env_key = os.getenv(ENV_API_KEY)
    if env_key:
        return env_key
    print(
        "Error: Bitquery API key is required.\n"
        "Please provide it via:\n"
        "  1. --api-key YOUR_API_KEY argument\n"
        "  2. BITQUERY_API_KEY environment variable\n"
        "\n"
        "Get your free API key at: https://bitquery.io/"
    )
    sys.exit(1)


def validate_address(address: str) -> bool:
    """Validate Ethereum/Cronos address format.
    
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
        # Handle both string and numeric inputs
        if isinstance(amount, str):
            # Check if it's already a decimal number (has a dot)
            if '.' in amount:
                # Already in human-readable format
                return f"{float(amount):.6f}"
            # Otherwise, it's in smallest units (wei/satoshi)
            amount_int = int(amount)
        else:
            amount_int = int(amount)
        
        # Convert from smallest unit to human-readable
        if decimals > 0:
            balance = amount_int / (10 ** decimals)
        else:
            balance = float(amount_int)
        
        # Return formatted with up to 6 decimal places, removing trailing zeros
        formatted = f"{balance:.6f}".rstrip('0').rstrip('.')
        return formatted if formatted else "0"
    except (ValueError, TypeError) as e:
        # If conversion fails, return the original value
        return str(amount)


def parse_currency(currency: Optional[Dict]) -> Dict[str, str]:
    """Parse currency information from Bitquery response.
    
    Args:
        currency: Currency dictionary from Bitquery GraphQL response
        
    Returns:
        Dictionary with parsed currency fields
    """
    if not currency:
        return {}
    result = {}
    if isinstance(currency, dict):
        result["name"] = currency.get("Name", "Unknown")
        result["symbol"] = currency.get("Symbol", "Unknown")
        result["decimals"] = str(currency.get("Decimals", 18))
        result["contract"] = currency.get("SmartContract", "")
    return result


def get_balances(api_key: str, address: str) -> Dict:
    """Get all token balances for an address using Bitquery API.
    
    Fetches all tokens with balance > 0 from Bitquery.
    Zero balance tokens are excluded.
    
    Args:
        api_key: Bitquery API key
        address: Wallet address to check
        
    Returns:
        Dictionary with balance information
    """
    try:
        variables = {
            "address": address,
        }
        payload = {
            "query": GET_USER_BALANCES_QUERY,
            "variables": variables,
        }
        
        # Determine API version and set headers/URL accordingly
        # API v2 tokens typically start with "ory_at_" and use Authorization header
        # API v1 tokens use X-API-KEY header
        is_v2_token = api_key.startswith("ory_at_") or api_key.startswith("Bearer ")
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if is_v2_token:
            # API v2 uses Authorization header with Bearer token
            if not api_key.startswith("Bearer "):
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers["Authorization"] = api_key
            api_url = BITQUERY_API_V2_URL
        else:
            # API v1 uses X-API-KEY header
            headers["X-API-KEY"] = api_key
            api_url = BITQUERY_API_V1_URL
        
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=30,
        )
        
        if response.status_code == 401:
            error_detail = "Unauthorized - Invalid API key. Please check your BITQUERY_API_KEY."
            try:
                error_data = response.json()
                if "errors" in error_data:
                    error_detail += f" Details: {json.dumps(error_data['errors'])}"
                elif "message" in error_data:
                    error_detail += f" Details: {error_data['message']}"
            except:
                error_detail += f" Response: {response.text[:200]}"
            return {
                "address": address,
                "error": error_detail,
                "success": False,
            }
        if response.status_code == 403:
            error_detail = "Forbidden - The API endpoint may require authentication or have access restrictions."
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
        
        # Parse Bitquery API v2 response structure
        ethereum_data = data.get("data", {}).get("ethereum", {})
        address_data = ethereum_data.get("address", [])
        
        if not address_data:
            return {
                "address": address,
                "balances": [],
                "success": True,
                "total_fetched": 0,
                "filtered_out": 0,
            }
        
        address_info = address_data[0]
        native_balance = address_info.get("balance", "0")
        balances_list = address_info.get("balances", [])
        
        # Transform Bitquery format to our standard format
        formatted_balances = []
        
        # Add native CRO balance first if > 0
        if native_balance and native_balance != "0":
            try:
                # Native balance is returned as a string, convert to int for processing
                native_balance_int = int(float(native_balance))
                if native_balance_int > 0:
                    formatted_balances.append({
                        "currency": {"name": "Cronos", "symbol": "CRO"},
                        "value": str(native_balance_int),
                        "symbol": "CRO",
                        "name": "Cronos",
                        "decimals": 18,
                        "contract": "",
                        "is_native": True,
                    })
            except (ValueError, TypeError):
                pass
        
        # Add token balances
        for balance in balances_list:
            currency = balance.get("currency", {})
            value = balance.get("value", "0")
            
            # Skip zero balances
            try:
                value_float = float(value)
                if value_float == 0:
                    continue
            except (ValueError, TypeError):
                continue
            
            # Get decimals - handle None or missing values
            decimals_raw = currency.get("decimals")
            if decimals_raw is None:
                decimals = 18  # Default for most tokens
            else:
                try:
                    decimals = int(decimals_raw)
                except (ValueError, TypeError):
                    decimals = 18
            
            # Bitquery v2 might return value in different formats
            # If value contains a decimal point, it's already formatted
            # Otherwise, it's in smallest units and needs conversion
            if isinstance(value, str) and '.' in value:
                # Already in decimal format, store as-is but convert to smallest unit for storage
                value_in_smallest = str(int(float(value) * (10 ** decimals)))
            else:
                # In smallest units (wei/satoshi), keep as-is
                value_in_smallest = str(int(value_float))
            
            formatted_balance = {
                "currency": currency,
                "value": value_in_smallest,  # Always store in smallest units for consistency
                "symbol": currency.get("symbol", "Unknown"),
                "name": currency.get("name", "Unknown"),
                "decimals": decimals,
                "contract": currency.get("address", ""),
                "is_native": False,
            }
            formatted_balances.append(formatted_balance)
        
        # Filter out test tokens
        def is_test_token(balance: Dict) -> bool:
            """Check if a token is a test token."""
            name = balance.get("name", "").lower()
            symbol = balance.get("symbol", "").lower()
            return "test" in name or (symbol.startswith("t") and len(symbol) > 1 and symbol[1:].isupper())
        
        filtered_balances = [b for b in formatted_balances if not is_test_token(b)]
        
        # Sort balances: native CRO first, then by value descending
        def sort_key(balance: Dict) -> tuple:
            """Sort key: native token first, then by value descending."""
            is_native = balance.get("is_native", False)
            try:
                value = float(balance.get("value", "0"))
            except (ValueError, TypeError):
                value = 0
            return (not is_native, -value)
        
        filtered_balances.sort(key=sort_key)
        
        return {
            "address": address,
            "balances": filtered_balances,
            "success": True,
            "total_fetched": len(filtered_balances),
            "filtered_out": len(formatted_balances) - len(filtered_balances),
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
    total_fetched = result.get("total_fetched", len(balances))
    if not balances:
        print(f"Address: {result['address']}")
        print("No balances found (all balances are 0)")
        return
    print(f"Address: {result['address']}")
    print(f"Found {len(balances)} token balance(s) (non-zero balances only)")
    filtered_out = result.get("filtered_out", 0)
    if filtered_out > 0:
        print(f"Note: {filtered_out} test token(s) filtered out (matching explorer behavior)")
    if total_fetched != len(balances) and filtered_out == 0:
        print(f"Total fetched: {total_fetched}")
    print()
    for idx, balance in enumerate(balances, 1):
        value = balance.get("value", "0")
        symbol = balance.get("symbol", "Unknown")
        name = balance.get("name", "Unknown")
        decimals = int(balance.get("decimals", 18))
        contract = balance.get("contract", "")
        
        # Format balance with proper precision
        try:
            value_int = int(value)
            if decimals > 0:
                balance_decimal = value_int / (10 ** decimals)
                # Use more precision for very small values
                if balance_decimal < 0.000001:
                    formatted_balance = f"{balance_decimal:.18f}".rstrip('0').rstrip('.')
                else:
                    formatted_balance = f"{balance_decimal:.6f}".rstrip('0').rstrip('.')
            else:
                formatted_balance = str(value_int)
        except (ValueError, TypeError):
            formatted_balance = str(value)
        
        print(f"{idx}. {name} ({symbol})")
        if contract:
            print(f"   Contract: {contract}")
        else:
            print(f"   Type: Native CRO")
        print(f"   Balance: {formatted_balance} {symbol}")
        print(f"   Value (raw): {value}")
        print(f"   Decimals: {decimals}")
        print()


def main() -> None:
    """Main function to get balance on Cronos blockchain."""
    parser = argparse.ArgumentParser(
        description="Get balance on Cronos blockchain using Bitquery API",
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
        "--api-key",
        type=str,
        default=None,
        help="Bitquery API key (or set BITQUERY_API_KEY environment variable)",
    )
    args = parser.parse_args()
    if not validate_address(args.address):
        print(f"Error: Invalid address format: {args.address}")
        print("Address must start with 0x and contain valid hexadecimal characters")
        sys.exit(1)
    
    network = args.network or os.getenv(ENV_NETWORK, DEFAULT_NETWORK)
    api_key = get_api_key(args.api_key)
    
    # Determine which API version based on token format
    is_v2 = api_key.startswith("ory_at_") or api_key.startswith("Bearer ")
    api_url = BITQUERY_API_V2_URL if is_v2 else BITQUERY_API_V1_URL
    api_version = "v2" if is_v2 else "v1"
    
    print(f"Using Bitquery API {api_version}: {api_url}")
    print(f"Network: {network}")
    print()
    
    result = get_balances(api_key, args.address)
    print_balance_result(result)


if __name__ == "__main__":
    main()

