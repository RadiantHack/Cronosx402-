"""
Facilitator Service for x402 Payment Protocol on Cronos Network

This service verifies and settles payment transactions on Cronos EVM network.
It implements the x402 facilitator protocol for EVM-based payments.
"""

import base64
import json
import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# Cronos Network RPC URL
CRONOS_RPC = os.getenv("CRONOS_RPC_URL", "https://evm.cronos.org")
CRONOS_CHAIN_ID = int(os.getenv("CRONOS_CHAIN_ID", "25"))  # 25=mainnet, 338=testnet


class FacilitatorService:
    """Service for verifying and settling x402 payments on Cronos Network."""

    def __init__(self, rpc_url: Optional[str] = None, facilitator_url: Optional[str] = None, settlement_key: Optional[str] = None):
        """Initialize the facilitator service.

        Args:
            rpc_url: Cronos Network RPC URL (defaults to mainnet)
            facilitator_url: Remote facilitator service URL (defaults to local)
            settlement_key: Optional private key for settlement (if None, runs in test mode)
        """
        self.rpc_url = rpc_url or CRONOS_RPC
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.settlement_key = settlement_key
        
        # Use frontend facilitator API by default
        if facilitator_url:
            self.facilitator_url = facilitator_url
        elif os.getenv("FACILITATOR_URL"):
            self.facilitator_url = os.getenv("FACILITATOR_URL")
        elif os.getenv("FRONTEND_URL"):
            self.facilitator_url = f"{os.getenv('FRONTEND_URL')}/api/facilitator"
        else:
            # Try to detect if running in Docker
            if os.path.exists("/.dockerenv"):
                # Running in Docker - use host.docker.internal (works on Mac/Windows)
                self.facilitator_url = "http://host.docker.internal:3000/api/facilitator"
            else:
                # Running locally
                self.facilitator_url = "http://localhost:3000/api/facilitator"

    def decode_payment_header(self, payment_header: str) -> Dict[str, Any]:
        """Decode base64-encoded payment header.

        Args:
            payment_header: Base64-encoded JSON payment header

        Returns:
            Decoded payment header dictionary

        Raises:
            ValueError: If header cannot be decoded
        """
        try:
            # Decode base64
            decoded_bytes = base64.b64decode(payment_header)
            decoded_str = decoded_bytes.decode("utf-8")
            # Parse JSON
            return json.loads(decoded_str)
        except Exception as e:
            raise ValueError(f"Failed to decode payment header: {str(e)}")

    def extract_transaction_info(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract transaction information from payment data.

        Args:
            payment_data: Decoded payment header

        Returns:
            Dictionary with transaction info (sender, recipient, amount, etc.)
        """
        payload = payment_data.get("payload", {})
        raw_tx_hex = payload.get("rawTransaction") or payload.get("transaction")

        if not raw_tx_hex:
            raise ValueError("Raw transaction not found in payment header")

        try:
            # Ensure hex format
            if not raw_tx_hex.startswith("0x"):
                raw_tx_hex = "0x" + raw_tx_hex

            # Recover sender address from signed transaction
            sender_address = self.w3.eth.account.recover_transaction(raw_tx_hex)
            
            return {
                "raw_tx": raw_tx_hex,
                "from": sender_address,
            }
        except Exception as e:
            raise ValueError(f"Failed to decode transaction: {str(e)}")

    def verify_evm_transaction(
        self, raw_tx_hex: str, payment_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify EVM transaction on Cronos Network.

        Args:
            raw_tx_hex: Hex-encoded signed transaction
            payment_requirements: Payment requirements from server

        Returns:
            Verification result with isValid, payer, etc.
        """
        try:
            # Ensure hex format
            if not raw_tx_hex.startswith("0x"):
                raw_tx_hex = "0x" + raw_tx_hex

            # Recover sender from signed transaction
            sender = self.w3.eth.account.recover_transaction(raw_tx_hex)

            # Decode the signed transaction using rlp (included in web3)
            from eth_account._utils.legacy_transactions import Transaction as LegacyTransaction
            
            # Convert hex to bytes for RLP decoding
            tx_bytes = bytes.fromhex(raw_tx_hex[2:] if raw_tx_hex.startswith("0x") else raw_tx_hex)
            
            # Decode the transaction - it's a signed transaction with signature
            # Remove the last 3 elements (v, r, s) to get the unsigned transaction fields
            import rlp
            decoded = rlp.decode(tx_bytes)
            
            # For legacy transactions: [nonce, gasPrice, gas, to, value, data, v, r, s]
            if len(decoded) >= 6:
                nonce = int.from_bytes(decoded[0], 'big') if decoded[0] else 0
                gas_price = int.from_bytes(decoded[1], 'big') if decoded[1] else 0
                gas = int.from_bytes(decoded[2], 'big') if decoded[2] else 0
                to_address = decoded[3].hex() if decoded[3] else ""
                value = int.from_bytes(decoded[4], 'big') if decoded[4] else 0
                data = decoded[5].hex() if decoded[5] else ""
                
                # Add 0x prefix to to_address
                if to_address and not to_address.startswith("0x"):
                    to_address = "0x" + to_address
            else:
                return {
                    "isValid": False,
                    "invalidReason": "Invalid transaction format",
                }

            # Get payment requirements
            required_pay_to = payment_requirements.get("payTo", "").lower()
            required_amount = int(payment_requirements.get("maxAmountRequired", "0"))
            required_asset = payment_requirements.get("asset", "CRO")

            # Verify recipient address
            if to_address.lower() != required_pay_to:
                return {
                    "isValid": False,
                    "invalidReason": f"Recipient mismatch: expected {required_pay_to}, got {to_address.lower()}",
                }

            # Verify amount (value is in wei)
            if value < required_amount:
                return {
                    "isValid": False,
                    "invalidReason": f"Amount insufficient: required {required_amount}, got {value}",
                }

            # Transaction is valid
            return {
                "isValid": True,
                "payer": sender,
                "to": to_address.lower(),
                "amount": str(value),
                "asset": required_asset,
            }
        except Exception as e:
            return {
                "isValid": False,
                "invalidReason": f"Verification error: {str(e)}",
            }

    def verify_payment(
        self, x402_version: int, payment_payload: Dict[str, Any], payment_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify a payment according to x402 protocol.

        Args:
            x402_version: x402 protocol version
            payment_payload: Payment header payload (decoded)
            payment_requirements: Payment requirements from server

        Returns:
            Verification response with isValid, payer, invalidReason
        """
        try:
            # Extract transaction from payload
            raw_tx_hex = payment_payload.get("rawTransaction") or payment_payload.get("transaction")

            if not raw_tx_hex:
                return {
                    "isValid": False,
                    "invalidReason": "Transaction not found in payment payload",
                }

            # Verify EVM transaction
            return self.verify_evm_transaction(raw_tx_hex, payment_requirements)
        except Exception as e:
            return {
                "isValid": False,
                "invalidReason": f"Verification failed: {str(e)}",
            }

    def settle_payment(
        self, x402_version: int, payment_payload: Dict[str, Any], payment_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Settle a payment (submit transaction to network).

        Args:
            x402_version: x402 protocol version
            payment_payload: Payment header payload (decoded)
            payment_requirements: Payment requirements from server

        Returns:
            Settlement response with success, txHash, etc.
        """
        try:
            # Extract raw transaction
            raw_tx_hex = payment_payload.get("rawTransaction") or payment_payload.get("transaction")
            
            if not raw_tx_hex:
                return {
                    "success": False,
                    "error": "Transaction not found in payment payload",
                }

            # Ensure hex format
            if not raw_tx_hex.startswith("0x"):
                raw_tx_hex = "0x" + raw_tx_hex

            print("\n" + "="*80)
            print("[FACILITATOR] SETTLEMENT REQUEST - CRONOS")
            print("="*80)
            print(f"[FACILITATOR] RPC URL: {self.rpc_url}")
            print(f"[FACILITATOR] Chain ID: {CRONOS_CHAIN_ID}")
            print(f"[FACILITATOR] x402Version: {x402_version}")
            print(f"[FACILITATOR] Raw transaction: {raw_tx_hex[:66]}...")
            print("\n[FACILITATOR] Payment Requirements:")
            print(json.dumps(payment_requirements, indent=2))
            print("="*80 + "\n")

            # In test mode (no settlement key), just verify without broadcasting
            if not self.settlement_key:
                print("[FACILITATOR] ⚠ Test mode: Skipping transaction broadcast (no settlement key configured)")
                print("[FACILITATOR] ✓ Payment verified successfully\n")
                return {
                    "success": True,
                    "txHash": "test_mode_no_broadcast",
                    "network": "cronos",
                    "message": "Test mode: Payment verified but not broadcast",
                }

            # Submit transaction to Cronos network
            tx_hash = self.w3.eth.send_raw_transaction(raw_tx_hex)
            tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, 'hex') else Web3.to_hex(tx_hash)

            print(f"[FACILITATOR] ✓ Transaction submitted: {tx_hash_hex}\n")

            return {
                "success": True,
                "txHash": tx_hash_hex,
                "network": "cronos",
                "explorerUrl": f"https://cronoscan.com/tx/{tx_hash_hex}",
            }
        except Exception as e:
            error_msg = str(e)
            print(f"[FACILITATOR] ✗ Settlement failed: {error_msg}\n")
            
            # Try to use remote facilitator as fallback
            try:
                settle_url = f"{self.facilitator_url}/settle"
                request_body = {
                    "x402Version": x402_version,
                    "paymentPayload": payment_payload,
                    "paymentRequirements": payment_requirements,
                }
                
                response = requests.post(
                    settle_url,
                    json=request_body,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result
                
                return {
                    "success": False,
                    "error": f"Local settlement failed: {error_msg}. Remote facilitator also failed with HTTP {response.status_code}",
                }
            except Exception as fallback_error:
                return {
                    "success": False,
                    "error": f"Settlement failed: {error_msg}. Fallback failed: {str(fallback_error)}",
                }

    def get_supported_networks(self) -> Dict[str, Any]:
        """Get supported networks and schemes.

        Returns:
            Dictionary with supported networks and schemes
        """
        return {
            "networks": ["cronos", "cronos-testnet"],
            "schemes": ["exact"],
        }
