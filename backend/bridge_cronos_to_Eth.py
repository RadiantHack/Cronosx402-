"""bridge_cronos_to_Eth.py

Simple Symbiosis bridge test script for Cronos <-> Ethereum.

Features:
- Query supported chains
- Query swap/bridge limits
- Generate bridge calldata via Symbiosis /v1/swap
- Optionally build and send the raw transaction using an RPC provider and a test private key
- Poll tx status via /v1/tx/{chainId}/{txHash}

Usage examples:

# Dry-run: generate calldata only
python bridge_cronos_to_Eth.py --source-chain 25 --dest-chain 1 --token 0x... --amount 0.25 --recipient 0xRECIPIENT

# Send the transaction (requires PRIVATE_KEY env var and RPC URLs)
PRIVATE_KEY="0x..." CRONOS_RPC_URL="https://evm-cronos.crypto.org" ETH_RPC_URL="https://mainnet.infura.io/v3/<KEY>" python bridge_cronos_to_Eth.py --source-chain 25 --dest-chain 1 --token 0x... --amount 0.25 --recipient 0xRECIPIENT --send-tx

Environment variables:
- SYMBIOSIS_API_URL (default https://api.symbiosis.finance)
- CRONOS_RPC_URL (required if --send-tx on source chain)
- ETH_RPC_URL (required if --send-tx to Ethereum)
- PRIVATE_KEY (required if --send-tx)

Note: Symbiosis public endpoints (e.g., /v1/chains, /v1/swap, /v1/tx/{chain}/{txHash}) do not require an API key for normal usage. Partner API keys are only necessary for higher rate limits or partner features.
NOTE: This script is for testing/development only. Do not use production funds or embed long-term private keys.
"""

import os
import time
import json
import argparse
import logging
from typing import Optional

import requests
from web3 import Web3
from web3.exceptions import TransactionNotFound
from decimal import Decimal

# Configuration
SYMBIOSIS_API_URL = os.getenv("SYMBIOSIS_API_URL", "https://api.symbiosis.finance")
# Symbiosis public endpoints do not require an API key for typical usage.
# Remove SYMBIOSIS_API_KEY unless you are a partner with an assigned key.
CRONOS_RPC_URL = os.getenv("CRONOS_RPC_URL", "https://evm-cronos.crypto.org")
ETH_RPC_URL = os.getenv("ETH_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

logger = logging.getLogger("bridge_test")
logging.basicConfig(level=logging.INFO, format="%(message)s")

HEADERS = {"Content-Type": "application/json"}
# Symbiosis public API endpoints (chains, swap, tx) generally do not require authentication.
# Keep headers minimal and avoid including an Authorization header by default.

# Token mapping (symbol -> {chainId: tokenAddress, "decimals": int})
# Add tokens here as needed. Addresses are examples for USDC on Cronos and Ethereum.
TOKEN_MAP = {
    "USDC": {
        25: "0xc21223249CA28397B4B6541dfFaEcC539BfF0c59",  # Cronos USDC
        1: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606e48",   # Ethereum USDC
        "decimals": 6,
    },
}



def get_chains() -> dict:
    url = f"{SYMBIOSIS_API_URL}/v1/chains"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_swap_limits(source_chain: int, dest_chain: int, token: str) -> dict:
    url = f"{SYMBIOSIS_API_URL}/v1/swap-limits"
    params = {
        "sourceChain": source_chain,
        "destChain": dest_chain,
        "token": token,
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def create_swap(
    source_chain: int,
    dest_chain: int,
    from_token: str,
    to_token: str,
    amount_raw: int,
    recipient: str,
    slippage_bps: int = 300,
) -> dict:
    """Request Symbiosis to create swap data.

    Uses the canonical schema required by Symbiosis (fromChainId, toChainId, fromTokenAddress, toTokenAddress).
    amount_raw should be an integer in smallest units for the source token.
    """
    url = f"{SYMBIOSIS_API_URL}/v1/swap"
    body = {
        "fromChainId": source_chain,
        "toChainId": dest_chain,
        "fromTokenAddress": from_token,
        "toTokenAddress": to_token,
        "amount": str(amount_raw),
        "recipient": recipient,
        "slippage": slippage_bps,
    }
    resp = requests.post(url, headers=HEADERS, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def poll_tx_status(chain_id: int, tx_hash: str, timeout: int = 300, interval: int = 6) -> dict:
    url = f"{SYMBIOSIS_API_URL}/v1/tx/{chain_id}/{tx_hash}"
    t0 = time.time()
    while True:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 404:
            logger.info("Status: not found yet, retrying...")
        else:
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status") or data
            logger.info(f"Polled status: {status}")
            return data
        if time.time() - t0 > timeout:
            raise TimeoutError("Timeout while polling transaction status")
        time.sleep(interval)


def get_token_decimals(rpc_url: str, token_address: str) -> Optional[int]:
    if not token_address:
        return None
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.isConnected():
        raise ConnectionError(f"RPC not connected: {rpc_url}")
    try:
        data = w3.eth.call({"to": Web3.toChecksumAddress(token_address), "data": "0x313ce567"})
        if not data or data == b"":
            return None
        return int(data.hex(), 16)
    except Exception as e:
        logger.debug(f"Could not fetch decimals via RPC for {token_address}: {e}")
        return None


# Minimal ERC20 ABI for approval & allowance checks
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
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
]


def get_allowance(rpc_url: str, token_address: str, owner: str, spender: str) -> int:
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.isConnected():
        raise ConnectionError(f"RPC not connected: {rpc_url}")
    contract = w3.eth.contract(address=Web3.toChecksumAddress(token_address), abi=ERC20_ABI)
    try:
        return int(contract.functions.allowance(Web3.toChecksumAddress(owner), Web3.toChecksumAddress(spender)).call())
    except Exception as e:
        logger.debug(f"Failed to read allowance for {token_address}: {e}")
        return 0


def build_approve_tx(rpc_url: str, token_address: str, owner: str, spender: str, amount: int) -> dict:
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    contract = w3.eth.contract(address=Web3.toChecksumAddress(token_address), abi=ERC20_ABI)
    data = contract.encodeABI(fn_name="approve", args=[Web3.toChecksumAddress(spender), int(amount)])
    nonce = w3.eth.get_transaction_count(Web3.toChecksumAddress(owner))
    tx = {
        "to": Web3.toChecksumAddress(token_address),
        "data": data,
        "value": 0,
        "nonce": nonce,
    }
    try:
        tx["chainId"] = w3.eth.chain_id
    except Exception:
        pass
    return tx


def decode_revert_reason(data_hex: str) -> str:
    """Decode revert reason from returned data if present (Error(string) selector 0x08c379a0)."""
    if not data_hex:
        return ""
    if data_hex.startswith("0x"):
        data_hex = data_hex[2:]
    # Error selector 08c379a0 -> abi-encoded string (offset, length, data)
    if data_hex.startswith("08c379a0"):
        try:
            # skip selector (4 bytes) and the offset (32 bytes)
            # length is at byte offset 4+32 = 36 bytes (72 hex chars)
            length_hex = data_hex[8 + 64:8 + 64 + 64]
            length = int(length_hex, 16)
            start = 8 + 64 + 64
            reason_hex = data_hex[start:start + (length * 2)]
            return bytes.fromhex(reason_hex).decode("utf-8", errors="replace")
        except Exception:
            return "(failed to decode revert reason)"
    return "(no revert reason)"


def simulate_call(w3: Web3, tx: dict, from_addr: str) -> Optional[str]:
    """Perform eth_call to simulate the transaction. Returns None on success or revert reason string on failure."""
    try:
        call_tx = tx.copy()
        call_tx["from"] = Web3.toChecksumAddress(from_addr)
        w3.eth.call(call_tx)
        return None
    except Exception as e:
        # Try to extract revert data
        err = e
        err_data = ""
        try:
            # web3 may include the data in args
            if hasattr(err, "args") and err.args:
                for a in err.args:
                    if isinstance(a, dict) and "data" in a:
                        # may have nested data
                        dat = a.get("data")
                        if isinstance(dat, dict):
                            # pick any nested value
                            for v in dat.values():
                                if isinstance(v, str) and v.startswith("0x"):
                                    err_data = v
                                    break
                        elif isinstance(dat, str) and dat.startswith("0x"):
                            err_data = dat
                            break
                    if isinstance(a, str) and a.startswith("0x"):
                        err_data = a
                        break
        except Exception:
            pass
        if not err_data:
            # last resort, try str(e)
            s = str(e)
            if "revert" in s:
                # try to extract hex blob
                idx = s.find("0x")
                if idx != -1:
                    err_data = s[idx:]
        if err_data:
            reason = decode_revert_reason(err_data)
            return reason
        return str(e)


def to_smallest(amount: str, decimals: int) -> int:
    # Accepts decimal strings and returns integer smallest units
    amt = Decimal(str(amount))
    mul = Decimal(10) ** decimals
    # Use quantize to avoid surprises
    return int((amt * mul).to_integral_value())


def estimate_gas_and_send(w3: Web3, tx: dict, private_key: str) -> str:
    # Estimate gas and send safely
    try:
        estimated = w3.eth.estimate_gas(tx)
        gas = int(estimated * 1.2)  # add 20% headroom
    except Exception:
        gas = tx.get("gas", 300000)
    tx["gas"] = gas
    try:
        tx["gasPrice"] = w3.eth.gas_price
    except Exception:
        pass
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return tx_hash.hex()


def send_raw_tx(rpc_url: str, to: str, data: str, value: int = 0) -> str:
    if not PRIVATE_KEY:
        raise RuntimeError("PRIVATE_KEY env var required to send transactions")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.isConnected():
        raise ConnectionError(f"RPC not connected: {rpc_url}")
    account = w3.eth.account.from_key(PRIVATE_KEY)
    nonce = w3.eth.get_transaction_count(account.address)

    tx = {
        "to": Web3.toChecksumAddress(to),
        "data": data,
        "value": int(value),
        "nonce": nonce,
        # gas/gasPrice/chainId will be set via estimate and RPC
    }

    # Fill chainId if available
    try:
        tx["chainId"] = w3.eth.chain_id
    except Exception:
        pass

    # Estimate gas and send using helper
    tx_hash_hex = estimate_gas_and_send(w3, tx, PRIVATE_KEY)
    logger.info(f"Sent raw tx: {tx_hash_hex}")
    return tx_hash_hex


def main():
    parser = argparse.ArgumentParser(description="Symbiosis bridge testing script")
    parser.add_argument("--source-chain", type=int, required=True)
    parser.add_argument("--dest-chain", type=int, required=True)
    parser.add_argument("--token", type=str, help="Token symbol (e.g., USDC). Must be in TOKEN_MAP, or use --from-token/--to-token")
    parser.add_argument("--from-token", type=str, help="Source token address (hex)")
    parser.add_argument("--to-token", type=str, help="Destination token address (hex)")
    parser.add_argument("--amount", type=str, required=True, help="Amount in token units (e.g., 0.25)")
    parser.add_argument("--recipient", type=str, required=True)
    parser.add_argument("--slippage", type=int, default=300, help="Slippage in basis points (default 300 = 3%)")
    parser.add_argument("--check-limits", action="store_true", help="Optional: call /v1/swap-limits before swap")
    parser.add_argument("--send-tx", action="store_true", help="Sign & send the generated tx via RPC (requires PRIVATE_KEY)")
    parser.add_argument("--auto-approve", action="store_true", help="Automatically send ERC20 approval if allowance is insufficient (requires PRIVATE_KEY)")
    parser.add_argument("--no-simulate", action="store_true", help="Do not simulate (eth_call) the transaction before sending")
    parser.add_argument("--dry-run", action="store_true", help="Only print calldata and do not send tx even if --send-tx provided")
    parser.add_argument("--list-chains", action="store_true", help="List supported chains and exit")
    args = parser.parse_args()

    if args.list_chains:
        chains = get_chains()
        print(json.dumps(chains, indent=2))
        return

    # Validate recipient & addresses
    if not args.recipient.startswith("0x"):
        raise SystemExit("Recipient must be a hex address starting with 0x")

    # Optional swap-limits check (not required; use --check-limits to opt-in)
    if args.check_limits:
        logger.info("Fetching swap limits (best-effort check)...")
        limits = get_swap_limits(args.source_chain, args.dest_chain, args.token or args.from_token or "")
        logger.info(json.dumps(limits, indent=2))

    # Resolve tokens: prefer mapping by symbol (--token), otherwise require from/to addresses
    from_token_addr = None
    to_token_addr = None
    decimals = None

    if args.token:
        symbol = args.token.upper()
        if symbol not in TOKEN_MAP:
            raise SystemExit(f"Token symbol '{symbol}' not found in TOKEN_MAP. Add mapping or use --from-token/--to-token")
        mapping = TOKEN_MAP[symbol]
        from_token_addr = mapping.get(args.source_chain)
        to_token_addr = mapping.get(args.dest_chain)
        decimals = mapping.get("decimals")
        if not from_token_addr or not to_token_addr:
            raise SystemExit(f"TOKEN_MAP for {symbol} does not include addresses for requested chains")
    else:
        # User supplied manual addresses
        if not (args.from_token and args.to_token):
            raise SystemExit("Either --token SYMBOL or both --from-token and --to-token addresses must be provided")
        from_token_addr = args.from_token
        to_token_addr = args.to_token

    # Determine token decimals via mapping or RPC if available
    rpc_for_source = CRONOS_RPC_URL if args.source_chain == 25 else (ETH_RPC_URL if args.source_chain == 1 else None)
    if decimals is None:
        try:
            if rpc_for_source:
                decimals = get_token_decimals(rpc_for_source, from_token_addr)
                logger.info(f"Resolved token decimals via RPC: {decimals}")
        except Exception as e:
            logger.warning(f"Could not fetch token decimals via RPC: {e}")

    if decimals is None:
        # fallback to 18 (dangerous) but inform the user
        decimals = 18
        logger.warning("Token decimals unknown; falling back to 18. This may cause incorrect amounts for tokens with different decimals.")

    amount_raw = to_smallest(args.amount, decimals)
    logger.info(f"Amount in smallest units: {amount_raw}")

    logger.info("Requesting swap calldata from Symbiosis...")
    swap_resp = create_swap(
        args.source_chain,
        args.dest_chain,
        from_token_addr,
        to_token_addr,
        amount_raw,
        args.recipient,
        slippage_bps=args.slippage,
    )
    logger.info("Symbiosis response:")
    logger.info(json.dumps(swap_resp, indent=2))

    # Symbiosis response contains tx object
    tx_obj = swap_resp.get("tx") or {}
    to = tx_obj.get("to")
    data = tx_obj.get("data")
    value = int(tx_obj.get("value", "0"))

    # Print summary
    logger.info(f"Transaction target: {to}")
    logger.info(f"Calldata present: {bool(data)}")
    logger.info(f"Value (wei): {value}")

    if args.send_tx and not args.dry_run:
        if not PRIVATE_KEY:
            raise SystemExit("PRIVATE_KEY env var is required to send transactions")
        if not to or not data:
            raise SystemExit("Swap response did not include tx target and calldata; cannot send")

        # Choose RPC URL based on source chain
        rpc_url = CRONOS_RPC_URL if args.source_chain == 25 else (ETH_RPC_URL if args.source_chain == 1 else None)
        if not rpc_url:
            raise SystemExit("No RPC URL configured for source chain; set CRONOS_RPC_URL or ETH_RPC_URL depending on the chain")

        # If token is ERC20 (value == 0) ensure approval
        is_erc20 = (value == 0)
        if is_erc20:
            owner_acct = Web3(Web3.HTTPProvider(rpc_url)).eth.account.from_key(PRIVATE_KEY)
            owner_addr = owner_acct.address
            spender = Web3.toChecksumAddress(to)
            allowance = get_allowance(rpc_url, from_token_addr, owner_addr, spender)
            logger.info(f"Current allowance for spender {spender}: {allowance}")
            if allowance < int(amount_raw):
                if args.auto_approve:
                    logger.info("Allowance insufficient, sending approve transaction...")
                    approve_tx = build_approve_tx(rpc_url, from_token_addr, owner_addr, spender, amount_raw)
                    # simulate approve
                    w3 = Web3(Web3.HTTPProvider(rpc_url))
                    reason = simulate_call(w3, approve_tx, owner_addr)
                    if reason:
                        raise SystemExit(f"Approve simulation failed: {reason}")
                    approve_hash = estimate_gas_and_send(w3, approve_tx, PRIVATE_KEY)
                    logger.info(f"Approve tx sent: {approve_hash}")
                    # Wait for confirmation (simple poll)
                    for _ in range(30):
                        try:
                            receipt = w3.eth.get_transaction_receipt(approve_hash)
                            if receipt and receipt.get("status") == 1:
                                logger.info("Approve confirmed")
                                break
                        except Exception:
                            pass
                        time.sleep(2)
                    else:
                        raise SystemExit("Approve did not confirm in time; aborting")
                else:
                    raise SystemExit("Token allowance insufficient for swap. Rerun with --auto-approve or approve the router manually.")

        # Build and simulate the swap tx (recommended) unless user opted out
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        acct = w3.eth.account.from_key(PRIVATE_KEY)
        nonce = w3.eth.get_transaction_count(acct.address)
        tx = {
            "to": Web3.toChecksumAddress(to),
            "data": data,
            "value": int(value),
            "nonce": nonce,
        }

        # Validate router address (basic check)
        if not Web3.isAddress(to):
            raise SystemExit("Swap target address invalid")

        if not args.no_simulate:
            sim_reason = simulate_call(w3, tx, acct.address)
            if sim_reason:
                raise SystemExit(f"Swap simulation failed (revert reason): {sim_reason}")
            logger.info("Swap simulation OK")

        tx_hash = estimate_gas_and_send(w3, tx, PRIVATE_KEY)
        logger.info(f"Sent tx: {tx_hash}")

        # Optionally poll bridge status (starting with source chain)
        logger.info("Polling Symbiosis for bridge status...")
        poll_resp = poll_tx_status(args.source_chain, tx_hash)
        logger.info("Poll response:")
        logger.info(json.dumps(poll_resp, indent=2))
    else:
        logger.info("Dry run or not sending tx — done.")


if __name__ == "__main__":
    main()
