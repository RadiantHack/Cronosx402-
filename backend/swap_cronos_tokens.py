#!/usr/bin/env python3
"""
Script to swap tokens on Cronos blockchain using VVS router.

This script uses the VVS router to swap native CRO to ERC20 tokens on Cronos.

ARCHITECTURE:
- VVS Router: Swap transaction building and execution (supports Cronos Mainnet & Testnet)
- web3.py: Transaction signing and submission
- ERC-20 Approvals: Automatic token approval handling (via VVS steps)
- Wrap/Unwrap: Native token wrapping support (TCRO ↔ WTCRO)

NETWORKS:
- Mainnet: Chain ID 25, Chain Name: "Cronos", RPC: https://evm.cronos.org
- Testnet: Chain ID 338, Chain Name: "Cronos Testnet", RPC: https://cronos-testnet.drpc.org
  (Note: Do NOT use evm-t3.cronos.org - it's behind Cloudflare anti-bot protection)

PRIVY INTEGRATION:
Since your application uses Privy for user onboarding, you have two options:

1. Export Private Key from Privy (for testing):
   In your frontend, use Privy's exportWallet() function:
   
   ```javascript
   import { exportWallet } from '@privy-io/react-auth';
   
   const privateKey = await exportWallet();
   // Then use this private key in the script
   ```
   
   Note: This requires user consent and is only available for embedded wallets.

2. Use a Separate Test Wallet:
   For testing purposes, create a separate wallet with test funds:
   - Generate a new private key
   - Fund it with testnet CRO from a faucet
   - Use this private key for testing the script

Reference:
- VVS Router: https://docs.vvs.finance
- Privy Docs: https://docs.privy.io/wallets/wallets/export

Usage:
    python swap_cronos_tokens.py <from_token> <to_token> <amount> <private_key> [options]
    
Examples:
    # Swap 1 CRO to USDC on MAINNET (default)
    python swap_cronos_tokens.py CRO USDC 1.0 <private_key>
    
    # Swap on TESTNET
    python swap_cronos_tokens.py CRO USDC 1.0 <private_key> --network testnet
    
    # Swap 100 USDC to CRO (ERC-20 token)
    python swap_cronos_tokens.py USDC CRO 100.0 <private_key> --from-address 0x...
    
    # Get quote only (dry-run)
    python swap_cronos_tokens.py CRO USDC 1.0 <private_key> --quote-only
    
    # Use custom slippage (default: 1%)
    python swap_cronos_tokens.py CRO USDC 1.0 <private_key> --slippage 0.5
"""

import argparse
import json
import os
import sys
from typing import Dict, Optional, Tuple
from decimal import Decimal

try:
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
except ImportError:
    print(
        "Error: 'web3' module not found. Please install dependencies:\n"
        "  python3 -m venv venv\n"
        "  source venv/bin/activate\n"
        "  pip install -e .\n"
        "Or install web3 directly:\n"
        "  pip install web3"
    )
    sys.exit(1)

try:
    import requests
except ImportError:
    print(
        "Error: 'requests' module not found. Please install dependencies:\n"
        "  pip install requests"
    )
    sys.exit(1)

# Constants
CRONOS_MAINNET_CHAIN_ID = 25
CRONOS_TESTNET_CHAIN_ID = 338
CRONOS_MAINNET_RPC = "https://evm.cronos.org"
# IMPORTANT: Do NOT use evm-t3.cronos.org - it's behind Cloudflare anti-bot
# Use real JSON-RPC infrastructure providers for testnet:
CRONOS_TESTNET_RPC = "https://cronos-testnet.drpc.org"  # dRPC - reliable infrastructure provider
# LI.FI uses 0x0000...0000 for native tokens (not 0xEeee...)
NATIVE_TOKEN_ADDRESS = "0x0000000000000000000000000000000000000000"
DEFAULT_SLIPPAGE = 1.0  # 1%
DEFAULT_NETWORK = "mainnet"

# Add retry and timeout defaults
DEFAULT_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2  # exponential backoff multiplier (seconds)
DEFAULT_RECEIPT_TIMEOUT = 120  # seconds to wait for receipt per attempt

# Common token addresses on Cronos Mainnet
CRONOS_MAINNET_TOKEN_ADDRESSES = {
    "CRO": NATIVE_TOKEN_ADDRESS,  # Native CRO
    "USDC": "0xc21223249CA28397B4B6541dfFaEcC539BfF0c59",
    "USDT": "0x66e428c3f67a68878562e79A0234c1F83c208770",
    "DAI": "0xF2001B145b43032AAF5Ee2884e456CCd805F677D",
    "WBTC": "0x062E66477Faf219F25E27e6b5C67602625781309",
    "WETH": "0xe44Fd7fCb2b1581822D0c862B68222998a0c299a",
}

# Common token addresses on Cronos Testnet
# Note: WTCRO (Wrapped TCRO) allows you to swap between native TCRO and wrapped TCRO
CRONOS_TESTNET_TOKEN_ADDRESSES = {
    "CRO": NATIVE_TOKEN_ADDRESS,  # Native TCRO
    "TCRO": NATIVE_TOKEN_ADDRESS,  # Alias for native CRO on testnet
    "WTCRO": "0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23",  # Wrapped TCRO (WETH9 contract)
    # Add more testnet token addresses as needed
    # "USDC": "0x...",
    # "USDT": "0x...",
}

# Minimal ERC-20 ABI for balance, allowance, approve, and decimals
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]


def get_network_config(network: str) -> Tuple[int, str, Dict[str, str]]:
    """Get network configuration (chain ID, RPC URL, token addresses).
    
    Args:
        network: Network name ("mainnet" or "testnet")
        
    Returns:
        Tuple of (chain_id, rpc_url, token_addresses_dict)
        
    Raises:
        SystemExit: If network is invalid
    """
    network_lower = network.lower()
    if network_lower == "mainnet":
        return (
            CRONOS_MAINNET_CHAIN_ID,
            CRONOS_MAINNET_RPC,
            CRONOS_MAINNET_TOKEN_ADDRESSES,
        )
    elif network_lower == "testnet":
        return (
            CRONOS_TESTNET_CHAIN_ID,
            CRONOS_TESTNET_RPC,
            CRONOS_TESTNET_TOKEN_ADDRESSES,
        )
    else:
        print(f"Error: Invalid network '{network}'. Use 'mainnet' or 'testnet'.")
        sys.exit(1)


def get_token_address(
    token_symbol: str,
    custom_address: Optional[str] = None,
    token_addresses: Optional[Dict[str, str]] = None,
) -> str:
    """Get token address for a given symbol.
    
    Args:
        token_symbol: Token symbol (e.g., "CRO", "USDC")
        custom_address: Optional custom token address
        token_addresses: Dictionary of token addresses for the network
        
    Returns:
        Token address (0x format)
        
    Raises:
        SystemExit: If token not found and no custom address provided
    """
    if custom_address:
        return Web3.to_checksum_address(custom_address)
    
    if not token_addresses:
        print("Error: Token addresses dictionary not provided.")
        sys.exit(1)
    
    token_upper = token_symbol.upper()
    if token_upper in token_addresses:
        return token_addresses[token_upper]
    
    print(
        f"Error: Token '{token_symbol}' not found in known tokens.\n"
        f"Known tokens: {', '.join(token_addresses.keys())}\n"
        f"Please use --from-address or --to-address to specify custom token addresses."
    )
    sys.exit(1)


def check_balance(
    w3: Web3,
    wallet_address: str,
    token_address: str,
    required_amount: int,
) -> bool:
    """Check if wallet has sufficient balance for the swap.
    
    Args:
        w3: Web3 instance
        wallet_address: Wallet address to check
        token_address: Token address (NATIVE_TOKEN_ADDRESS for native)
        required_amount: Required amount in smallest units
        
    Returns:
        True if balance is sufficient, False otherwise
    """
    try:
        if token_address == NATIVE_TOKEN_ADDRESS:
            # Check native token balance
            balance = w3.eth.get_balance(wallet_address)
            if balance < required_amount:
                print(f"Error: Insufficient native token balance.")
                print(f"  Required: {required_amount} wei")
                print(f"  Available: {balance} wei")
                return False
        else:
            # Check ERC-20 token balance
            token_contract = w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=ERC20_ABI,
            )
            balance = token_contract.functions.balanceOf(wallet_address).call()
            if balance < required_amount:
                print(f"Error: Insufficient token balance.")
                print(f"  Required: {required_amount}")
                print(f"  Available: {balance}")
                return False
        
        return True
    except Exception as e:
        print(f"Warning: Could not check balance: {e}")
        # Don't block execution if balance check fails
        return True


# Add VVS defaults (mainnet)
VVS_ROUTER_ADDRESS = Web3.to_checksum_address("0x145863Eb42Cf62847A6Ca784e6416C1682b1b2Ae")
VVS_WCRO = Web3.to_checksum_address("0x5C7F8A570d578ED84E63fdFA7b1eE72dEae1AE23")

# Extend VVS_ROUTER_ABI with token swap methods
VVS_ROUTER_ABI = [
    {
        "name": "getAmountsOut",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path", "type": "address[]"},
        ],
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
    },
    {
        "name": "swapExactETHForTokens",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
    },
    {
        "name": "swapExactTokensForETH",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
    },
    {
        "name": "swapExactTokensForTokens",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
    },
]


def _find_working_path(router, amount_in: int, candidate_paths: list):
	"""Try candidate paths in order and return (path, amounts_out) for first that succeeds."""
	for p in candidate_paths:
		try:
			amounts = router.functions.getAmountsOut(amount_in, p).call()
			return p, amounts
		except Exception:
			# path not available / no pair, try next
			continue
	raise ValueError("No valid path found from candidates")


def ensure_token_approval(
	w3: Web3,
	token_address: str,
	owner_address: str,
	private_key: str,
	spender: str,
	required_amount: int,
	retries: int = DEFAULT_RETRIES,
) -> bool:
	"""Ensure the router has allowance to spend owner's ERC-20 tokens.
	Retry on transient errors. Returns True if approval exists or was successful."""
	try:
		token = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
		allowance = token.functions.allowance(owner_address, spender).call()
		if allowance >= required_amount:
			return True

		print(f"Approval required: current allowance {allowance}, required {required_amount}. Sending approve tx...")
		max_approval = 2 ** 256 - 1

		for attempt in range(1, retries + 1):
			try:
				nonce = w3.eth.get_transaction_count(owner_address)
				approve_tx = token.functions.approve(Web3.to_checksum_address(spender), max_approval).build_transaction(
					{
						"from": owner_address,
						"nonce": nonce,
						"gas": 100000,
						"gasPrice": w3.eth.gas_price,
						"chainId": w3.eth.chain_id,
					}
				)
				signed = w3.eth.account.sign_transaction(approve_tx, private_key)
				raw = getattr(signed, "raw_transaction", getattr(signed, "rawTransaction", None))
				tx_hash = w3.eth.send_raw_transaction(raw)
				print(f"Approve tx sent: {tx_hash.hex()}. Waiting for confirmation...")
				receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=DEFAULT_RECEIPT_TIMEOUT)
				if receipt.status == 1:
					print("Approve confirmed.")
					return True
				else:
					print(f"Approve tx failed (status={receipt.status}).")
					return False
			except Exception as e:
				print(f"Approve attempt {attempt} failed: {e}")
				if attempt < retries:
					sleep_time = RETRY_BACKOFF_FACTOR ** (attempt - 1)
					print(f"Retrying approve in {sleep_time}s...")
					__import__("time").sleep(sleep_time)
				else:
					print("Exceeded approval retries.")
					return False
	except Exception as e:
		print(f"Error during token approval check: {e}")
		return False


def execute_vvs_swap(
	w3: Web3,
	from_amount_wei: int,
	from_token: str,
	to_token: str,
	private_key: str,
	slippage_pct: float,
	vvs_router_address: str = VVS_ROUTER_ADDRESS,
	simulate: bool = False,
	retries: int = DEFAULT_RETRIES,
) -> Optional[dict]:
	"""Execute swap via VVS router for CRO->ERC20, ERC20->CRO, and ERC20->ERC20.
	Returns a JSON-serializable summary dict on success, None on failure."""
	try:
		account = w3.eth.account.from_key(private_key)
		user_address = account.address
		router = w3.eth.contract(address=Web3.to_checksum_address(vvs_router_address), abi=VVS_ROUTER_ABI)
		deadline = int(__import__("time").time()) + 300  # 5 minutes

		# Prepare candidate paths (prefer direct [A,B])
		if from_token == NATIVE_TOKEN_ADDRESS and to_token != NATIVE_TOKEN_ADDRESS:
			candidates = [[VVS_WCRO, Web3.to_checksum_address(to_token)]]
		elif from_token != NATIVE_TOKEN_ADDRESS and to_token == NATIVE_TOKEN_ADDRESS:
			# prefer direct [token, WCRO]
			candidates = [[Web3.to_checksum_address(from_token), VVS_WCRO]]
		else:
			# ERC20 -> ERC20: try direct [A,B] then via WCRO [A,WCRO,B]
			candidates = [[Web3.to_checksum_address(from_token), Web3.to_checksum_address(to_token)], [Web3.to_checksum_address(from_token), VVS_WCRO, Web3.to_checksum_address(to_token)]]

		# Find a working path
		path, amounts_out = _find_working_path(router, from_amount_wei, candidates)
		expected_out = int(amounts_out[-1])
		amount_out_min = int(expected_out * (1 - slippage_pct / 100.0))

		# Select function based on flow
		if from_token == NATIVE_TOKEN_ADDRESS and to_token != NATIVE_TOKEN_ADDRESS:
			func = router.functions.swapExactETHForTokens(amount_out_min, path, user_address, deadline)
			tx_base_kwargs = {"from": user_address, "value": from_amount_wei}
		elif from_token != NATIVE_TOKEN_ADDRESS and to_token == NATIVE_TOKEN_ADDRESS:
			# ensure approval
			if not ensure_token_approval(w3, from_token, user_address, private_key, Web3.to_checksum_address(vvs_router_address), from_amount_wei):
				print("Approval failed, aborting swap.")
				return None
			func = router.functions.swapExactTokensForETH(from_amount_wei, amount_out_min, path, user_address, deadline)
			tx_base_kwargs = {"from": user_address}
		else:  # ERC20 -> ERC20
			if from_token == Web3.to_checksum_address(to_token):
				print("From and To tokens are identical; nothing to swap.")
				return None
			if not ensure_token_approval(w3, from_token, user_address, private_key, Web3.to_checksum_address(vvs_router_address), from_amount_wei):
				print("Approval failed, aborting swap.")
				return None
			func = router.functions.swapExactTokensForTokens(from_amount_wei, amount_out_min, path, user_address, deadline)
			tx_base_kwargs = {"from": user_address}

		# Estimate gas and build tx (estimate may fail; fallback to default)
		try:
			gas_estimate = func.estimate_gas(tx_base_kwargs)
		except Exception:
			gas_estimate = 300000

		# Build tx template (nonce & gasPrice set per attempt)
		tx_base_kwargs.update({"gas": int(gas_estimate)})

		print("VVS swap transaction:")
		print(f"  Router: {vvs_router_address}")
		print(f"  Path: {path}")
		if from_token == NATIVE_TOKEN_ADDRESS:
			print(f"  Value (wei): {from_amount_wei}")
		else:
			print(f"  Amount In (wei): {from_amount_wei}")
		print(f"  Expected Out (wei): {expected_out}")
		print(f"  Min Out (wei): {amount_out_min}")
		print(f"  Gas (estimate): {gas_estimate}")

		if simulate:
			print("Simulation mode: not sending transaction.")
			return {
				"status": "simulated",
				"amountIn": str(from_amount_wei),
				"expectedOut": str(expected_out),
				"amountOutMin": str(amount_out_min),
				"gasEstimate": gas_estimate,
				"path": [p for p in path],
			}

		# Send & wait with retries
		last_err = None
		for attempt in range(1, retries + 1):
			try:
				# set nonce/gasPrice fresh each attempt
				tx_kwargs = dict(tx_base_kwargs)
				tx_kwargs["nonce"] = w3.eth.get_transaction_count(user_address)
				tx_kwargs["gasPrice"] = w3.eth.gas_price
				tx = func.build_transaction(tx_kwargs)

				signed = w3.eth.account.sign_transaction(tx, private_key)
				raw_tx = getattr(signed, "raw_transaction", getattr(signed, "rawTransaction", None))
				tx_hash = w3.eth.send_raw_transaction(raw_tx)
				print(f"Transaction sent: {tx_hash.hex()}")
				receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=DEFAULT_RECEIPT_TIMEOUT)
				if receipt.status != 1:
					print(f"Swap transaction reverted (status={receipt.status})")
					return None
				# Success: return summary
				summary = {
					"status": "success",
					"txHash": tx_hash.hex(),
					"amountIn": str(from_amount_wei),
					"expectedOut": str(expected_out),
					"amountOutMin": str(amount_out_min),
					"gasEstimate": gas_estimate,
					"gasUsed": receipt.gasUsed,
					"blockNumber": receipt.blockNumber,
					"path": [p for p in path],
				}
				print(json.dumps(summary))
				return summary
			except Exception as e:
				last_err = e
				print(f"Swap attempt {attempt} failed: {e}")
				if attempt < retries:
					sleep_time = RETRY_BACKOFF_FACTOR ** (attempt - 1)
					print(f"Retrying swap in {sleep_time}s...")
					__import__("time").sleep(sleep_time)
				else:
					print("Exceeded swap retries.")
					break

		print(f"Swap failed after {retries} attempts: {last_err}")
		return None
	except Exception as e:
		print(f"Error executing VVS swap: {e}")
		return None


def check_rpc_connectivity(rpc_url: str, timeout: int = 6, debug: bool = False) -> Tuple[bool, str]:
    """Quick RPC test using eth_chainId. Returns (True, chainId_hex) or (False, error)."""
    try:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []}
        resp = requests.post(rpc_url, json=payload, timeout=timeout)
        if debug:
            print(f"[RPC DEBUG] POST {rpc_url} -> {resp.status_code} {resp.text[:1000]}")
        # Detect HTML pages (Cloudflare / captive pages) and return a friendly message
        content_type = resp.headers.get("content-type", "")
        text_lower = (resp.text or "").lower()
        if "text/html" in content_type or "<!doctype html" in text_lower or "cloudflare" in text_lower or "attention required" in text_lower:
            return False, "Endpoint returned an HTML page (likely Cloudflare protection). This RPC is not usable for programmatic JSON-RPC calls."
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        if "result" in data:
            return True, data["result"]
        return False, f"Unexpected JSON-RPC response: {data}"
    except requests.exceptions.RequestException as e:
        return False, str(e)


def main() -> None:
    """Main function to swap native CRO -> ERC20 via VVS (swapExactETHForTokens)."""
    parser = argparse.ArgumentParser(
        description="Swap native CRO -> token on Cronos using VVS router",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("from_token", type=str, help="Source token symbol (CRO or ERC-20 symbol/address)")
    parser.add_argument("to_token", type=str, help="Destination token symbol (e.g., USDC)")
    parser.add_argument("amount", type=float, help="Amount to swap (in human-readable format, e.g., 1.0 for 1 CRO)")
    parser.add_argument("private_key", type=str, help="Private key for signing transactions (0x format)")
    parser.add_argument("--from-address", type=str, default=None, help="Custom source token address (unused; CRO required)")
    parser.add_argument("--to-address", type=str, default=None, help="Custom destination token address (overrides to_token symbol)")
    parser.add_argument("--slippage", type=float, default=DEFAULT_SLIPPAGE, help=f"Slippage tolerance percentage (default: {DEFAULT_SLIPPAGE}%)")
    parser.add_argument("--network", type=str, choices=["mainnet", "testnet"], default=None, help=f"Network to use (default: {DEFAULT_NETWORK})")
    parser.add_argument("--rpc-url", type=str, default=None, help="Custom Cronos RPC URL (overrides network default)")
    parser.add_argument("--simulate", action="store_true", help="Simulate swap without sending transaction")
    parser.add_argument("--rpc-timeout", type=int, default=6, help="RPC request timeout in seconds (default: 6)")
    parser.add_argument("--rpc-debug", action="store_true", help="Show raw RPC request/response for debugging")
    parser.add_argument(
        "--skip-balance-check",
        action="store_true",
        help="Skip the pre-swap balance check (not recommended)",
    )
    parser.add_argument("--vvs-router", type=str, default=None, help="Custom VVS router address (overrides default)")
    args = parser.parse_args()

    # Determine network
    network = args.network or os.getenv("CRONOS_NETWORK", DEFAULT_NETWORK)
    chain_id, default_rpc, token_addresses = get_network_config(network)
    # Prefer CLI --rpc-url, then CRONOS_RPC env var, then network default
    rpc_url = args.rpc_url or os.getenv("CRONOS_RPC") or default_rpc
    rpc_timeout = args.rpc_timeout
    rpc_debug = args.rpc_debug

    print(f"Network: {network.upper()}")
    print(f"Chain ID: {chain_id}")
    print(f"RPC URL: {rpc_url}")
    print()

    # Quick RPC connectivity test and fallback logic
    print("Testing RPC endpoint (eth_chainId)...")
    ok, info = check_rpc_connectivity(rpc_url, timeout=rpc_timeout, debug=rpc_debug)
    if not ok:
        print(f"Warning: RPC test failed for {rpc_url}: {info}")
        # Try small list of known public fallbacks
        # include user-suggested endpoints for automatic retry
        fallbacks = [
            default_rpc,
            "https://cronos-evm.publicnode.com",
            "https://cronos.blockpi.network/v1/rpc/public",
            "https://rpc.vvs.finance",
            "https://rpc.cronos.org",
            "https://evm.cronos.org",
        ]
        used = None
        for fb in fallbacks:
            if fb == rpc_url:
                continue
            print(f"Trying fallback RPC: {fb}")
            ok_fb, info_fb = check_rpc_connectivity(fb, timeout=rpc_timeout, debug=rpc_debug)
            if ok_fb:
                print(f"Using fallback RPC: {fb} (chainId: {info_fb})")
                rpc_url = fb
                used = fb
                break
            else:
                print(f"Fallback {fb} failed: {info_fb}")
        if not used:
            print("\nError: Could not connect to any Cronos RPC endpoints.")
            print("Likely causes:")
            print("  - The public Cronos RPC endpoint is protected by Cloudflare and blocks programmatic requests.")
            print("  - Network or ISP restrictions.")
            print("What you can try:")
            print("  - Use a third-party RPC provider (QuickNode, Ankr, Chainstack, NodeReal/dRPC) which provides programmatic endpoints.")
            print("  - Provide a working RPC with --rpc-url or set CRONOS_RPC environment variable.")
            print("    Example (Linux/macOS): export CRONOS_RPC=\"https://your-provider-endpoint\"")
            print("    Example (Windows cmd): setx CRONOS_RPC \"https://your-provider-endpoint\"")
            print("  - Run this curl to inspect the RPC response:")
            print("    curl -X POST --data '{\"jsonrpc\":\"2.0\",\"method\":\"eth_chainId\",\"params\":[],\"id\":1}' -H \"Content-Type: application/json\" https://evm.cronos.org")
            sys.exit(1)
    else:
        print(f"RPC looks healthy (chainId: {info})")

    # Connect to Cronos (use provided timeout to avoid long hangs)
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": rpc_timeout}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    try:
        if not w3.is_connected():
            print(f"Error: Could not connect via web3 to Cronos RPC: {rpc_url}")
            print("Note: The RPC might respond to JSON-RPC but reject some provider headers/requests.")
            print("You can try a different endpoint with --rpc-url or enable --rpc-debug to see raw responses.")
            sys.exit(1)
    except Exception as e:
        print(f"Error while checking provider connection: {e}")
        sys.exit(1)

    print(f"Connected to Cronos {network.upper()} (Chain ID: {chain_id})")
    print()
    
    # Validate private key
    if not args.private_key.startswith("0x"):
        args.private_key = "0x" + args.private_key
    
    try:
        account = Web3().eth.account.from_key(args.private_key)
        wallet_address = account.address
        print(f"Wallet Address: {wallet_address}")
    except Exception as e:
        print(f"Error: Invalid private key: {e}")
        sys.exit(1)
    
    # Resolve token addresses (only CRO -> token is supported)
    from_token_address = get_token_address(args.from_token, args.from_address, token_addresses)
    to_token_address = get_token_address(args.to_token, args.to_address, token_addresses)

    print(f"From Token: {args.from_token} ({from_token_address})")
    print(f"To Token: {args.to_token} ({to_token_address})")
    print(f"Amount: {args.amount}")
    print(f"Slippage: {args.slippage}%")
    print()

    # Now supports CRO (native) and ERC-20 as source tokens (ERC20->CRO and ERC20->ERC20 are supported)

    # Get token decimals (for native token, assume 18)
    from_decimals = 18
    if from_token_address != NATIVE_TOKEN_ADDRESS:
        try:
            token_contract = w3.eth.contract(
                address=from_token_address,
                abi=ERC20_ABI,
            )
            from_decimals = token_contract.functions.decimals().call()
        except Exception as e:
            print(f"Warning: Could not get decimals for from_token, using 18: {e}")

    to_decimals = 18
    if to_token_address != NATIVE_TOKEN_ADDRESS:
        try:
            token_contract = w3.eth.contract(
                address=to_token_address,
                abi=ERC20_ABI,
            )
            to_decimals = token_contract.functions.decimals().call()
        except Exception as e:
            print(f"Warning: Could not get decimals for to_token, using 18: {e}")

    # Convert amount to smallest units using source token decimals
    amount_wei = int(Decimal(str(args.amount)) * Decimal(10 ** from_decimals))
    print(f"Amount (wei): {amount_wei}\n")

    # Check balance (ensure wallet has enough source token)
    if not args.skip_balance_check:
        print("Checking balance...")
        if not check_balance(w3, wallet_address, from_token_address, amount_wei):
            sys.exit(1)
        print("Balance sufficient.\n")

    # Execute VVS swap
    print("Executing VVS swap...")
    vvs_router_addr = Web3.to_checksum_address(args.vvs_router) if args.vvs_router else VVS_ROUTER_ADDRESS
    result = execute_vvs_swap(
        w3=w3,
        from_amount_wei=amount_wei,
        from_token=from_token_address,
        to_token=to_token_address,
        private_key=args.private_key,
        slippage_pct=args.slippage,
        vvs_router_address=vvs_router_addr,
        simulate=args.simulate,
    )
    if not result:
        print("\n❌ VVS swap failed.")
        sys.exit(1)
    
    # result is a dict summary (or simulated summary)
    if isinstance(result, dict):
        status = result.get("status")
        if status == "simulated":
            print("\nSimulation complete: no transaction sent.")
            print("Simulation summary:")
            print(json.dumps(result, indent=2))
            return
        elif status == "success":
            tx_hash = result.get("txHash")
            print("\n✅ Swap completed via VVS!")
            print(f"Transaction Hash: {tx_hash}")
            print(f"Gas Used: {result.get('gasUsed')}, Block: {result.get('blockNumber')}")
            print("Swap summary (JSON):")
            print(json.dumps(result, indent=2))
            if network == "mainnet":
                print(f"View on Cronoscan: https://cronoscan.com/tx/{tx_hash}")
            else:
                print(f"View on Testnet Explorer: https://testnet.cronoscan.com/tx/{tx_hash}")
            return
        else:
            print(f"\nUnexpected result status: {status}")
            print(json.dumps(result, indent=2))
            sys.exit(1)
    else:
        # Fallback (shouldn't occur with current execute_vvs_swap)
        print("\n✅ Swap result:", result)
        return


# Add program entry point if missing
if __name__ == "__main__":
    main()
