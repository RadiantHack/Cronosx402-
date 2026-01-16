"""
FacilitatorService - Payment verification and settlement for x402 Paytech.

Supports multiple blockchain networks:
- Cronos (EVM): Native CRO and ERC20 transfers


This service handles:
1. Payment requirement validation
2. Transaction verification against requirements
3. Settlement and confirmation
"""

import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from web3 import Web3
from web3.types import TxData
from eth_account import Account
from eth_keys import keys

logger = logging.getLogger(__name__)


class NetworkType(str, Enum):
    """Supported blockchain networks."""
    CRONOS = "cronos"
    MOVEMENT = "movement"


@dataclass
class PaymentRequirements:
    """Payment requirements that must be satisfied by a transaction."""
    network: NetworkType
    asset: str  # Native symbol (e.g., "CRO") or ERC20 address (0x...)
    amount: int  # Amount in smallest unit (wei for EVM)
    pay_to: str  # Recipient address (0x... for EVM)
    chain_id: int
    max_timeout_seconds: Optional[int] = None


@dataclass
class PaymentVerificationResult:
    """Result of payment verification."""
    is_valid: bool
    tx_hash: str
    network: str
    from_address: str
    to_address: str
    amount: str
    asset: str
    error_message: Optional[str] = None


class CronosPaymentVerifier:
    """Verifies Cronos (EVM) payments using Web3.py."""

    def __init__(self, rpc_url: str):
        """Initialize with Cronos RPC endpoint.
        
        Args:
            rpc_url: HTTP(S) URL to Cronos RPC node
        """
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to Cronos RPC: {rpc_url}")
        logger.info(f"Connected to Cronos RPC: {rpc_url}")

    def verify_payment(
        self,
        requirements: PaymentRequirements,
        raw_tx_hex: str,
        tx_signature: str,
    ) -> PaymentVerificationResult:
        """Verify a Cronos payment transaction.
        
        Args:
            requirements: Payment requirements that must be satisfied
            raw_tx_hex: Raw transaction in hex format (0x-prefixed or not)
            tx_signature: Transaction signature
            
        Returns:
            PaymentVerificationResult with verification status
        """
        try:
            # Ensure hex format
            if not raw_tx_hex.startswith("0x"):
                raw_tx_hex = "0x" + raw_tx_hex

            # Decode the raw transaction
            tx_data = self.w3.eth.account.decode_transaction(raw_tx_hex)
            logger.info(f"Decoded transaction: {tx_data}")

            # Recover sender address
            from_address = self._recover_sender(raw_tx_hex, tx_signature)
            if not from_address:
                raise ValueError("Failed to recover sender address")

            # Validate chain ID
            if tx_data.get("chainId") != requirements.chain_id:
                raise ValueError(
                    f"Chain ID mismatch: tx={tx_data.get('chainId')}, "
                    f"required={requirements.chain_id}"
                )

            # Verify based on asset type
            if requirements.asset.lower().startswith("0x"):
                # ERC20 transfer
                self._verify_erc20_transfer(
                    tx_data, 
                    requirements.asset,
                    requirements.pay_to,
                    requirements.amount
                )
            else:
                # Native CRO transfer
                self._verify_native_transfer(
                    tx_data,
                    requirements.pay_to,
                    requirements.amount
                )

            # Verify nonce is not stale (optional)
            current_nonce = self.w3.eth.get_transaction_count(from_address)
            if tx_data.get("nonce") < current_nonce - 128:  # Stale if too old
                raise ValueError(f"Transaction nonce is stale: {tx_data.get('nonce')}")

            # Extract amount for response
            if requirements.asset.lower().startswith("0x"):
                amount_str = str(requirements.amount)
                asset_str = requirements.asset
            else:
                amount_str = str(tx_data.get("value", 0))
                asset_str = "CRO"

            return PaymentVerificationResult(
                is_valid=True,
                tx_hash=self.w3.keccak(hexstr=raw_tx_hex).hex(),
                network="cronos",
                from_address=from_address,
                to_address=tx_data.get("to", ""),
                amount=amount_str,
                asset=asset_str,
            )

        except Exception as e:
            error_msg = f"Payment verification failed: {str(e)}"
            logger.error(error_msg)
            return PaymentVerificationResult(
                is_valid=False,
                tx_hash="",
                network="cronos",
                from_address="",
                to_address="",
                amount="0",
                asset="",
                error_message=error_msg,
            )

    def settle_payment(
        self,
        raw_tx_hex: str,
    ) -> Dict[str, Any]:
        """Settle (submit) a verified payment transaction.
        
        Args:
            raw_tx_hex: Raw transaction in hex format
            
        Returns:
            Dictionary with tx_hash and network
        """
        try:
            if not raw_tx_hex.startswith("0x"):
                raw_tx_hex = "0x" + raw_tx_hex

            # Send the transaction
            tx_hash = self.w3.eth.send_raw_transaction(raw_tx_hex)
            logger.info(f"Transaction submitted: {tx_hash.hex()}")

            return {
                "tx_hash": tx_hash.hex(),
                "network": "cronos",
                "status": "submitted",
            }
        except Exception as e:
            error_msg = f"Settlement failed: {str(e)}"
            logger.error(error_msg)
            return {
                "tx_hash": "",
                "network": "cronos",
                "status": "failed",
                "error": error_msg,
            }

    def _verify_native_transfer(
        self,
        tx_data: TxData,
        expected_to: str,
        expected_amount: int,
    ) -> None:
        """Verify a native CRO transfer transaction.
        
        Raises:
            ValueError if transaction doesn't match requirements
        """
        to_address = tx_data.get("to")
        value = tx_data.get("value", 0)

        # Verify recipient
        if to_address.lower() != expected_to.lower():
            raise ValueError(
                f"Recipient mismatch: tx sends to {to_address}, "
                f"expected {expected_to}"
            )

        # Verify amount
        if value < expected_amount:
            raise ValueError(
                f"Amount insufficient: tx transfers {value}, "
                f"required {expected_amount}"
            )

        logger.info(f"Native transfer verified: {value} CRO to {to_address}")

    def _verify_erc20_transfer(
        self,
        tx_data: TxData,
        erc20_contract: str,
        recipient: str,
        amount: int,
    ) -> None:
        """Verify an ERC20 transfer transaction.
        
        Decodes the transaction data to extract transfer parameters.
        Expects transfer(address,uint256) function signature.
        
        Raises:
            ValueError if transaction doesn't match requirements
        """
        data = tx_data.get("data", "")
        if not data or not data.startswith("0xa9059cbb"):
            raise ValueError("Not an ERC20 transfer transaction (invalid function selector)")

        to_address = tx_data.get("to")
        if to_address.lower() != erc20_contract.lower():
            raise ValueError(
                f"Contract mismatch: tx calls {to_address}, "
                f"expected {erc20_contract}"
            )

        # Decode transfer parameters (simple ABI decoding)
        try:
            # Function selector is 4 bytes (a9059cbb), followed by params
            # Each param is 32 bytes (256 bits)
            params = data[10:]  # Skip 0x + 4-byte selector
            
            # Extract recipient (first 32 bytes, padded to left)
            recipient_param = "0x" + params[24:64]
            # Extract amount (second 32 bytes)
            amount_param = int(params[64:128], 16)

            # Verify recipient
            if recipient_param.lower() != recipient.lower():
                raise ValueError(
                    f"Recipient mismatch: tx sends to {recipient_param}, "
                    f"expected {recipient}"
                )

            # Verify amount
            if amount_param < amount:
                raise ValueError(
                    f"Amount insufficient: tx transfers {amount_param}, "
                    f"required {amount}"
                )

            logger.info(
                f"ERC20 transfer verified: {amount_param} tokens "
                f"to {recipient_param}"
            )
        except Exception as e:
            raise ValueError(f"Failed to decode ERC20 transfer: {str(e)}")

    def _recover_sender(
        self,
        raw_tx_hex: str,
        signature_hex: str,
    ) -> Optional[str]:
        """Recover sender address from transaction and signature.
        
        Args:
            raw_tx_hex: Raw transaction in hex
            signature_hex: Signature in hex
            
        Returns:
            Recovered sender address or None if recovery fails
        """
        try:
            # Decode transaction to get the message hash
            tx_data = self.w3.eth.account.decode_transaction(raw_tx_hex)
            
            # Get transaction hash (this is what was signed)
            tx_hash = self.w3.keccak(hexstr=raw_tx_hex)
            
            # Recover address from signature
            # signature format: 0x + 130 hex chars (65 bytes: r + s + v)
            if signature_hex.startswith("0x"):
                signature_hex = signature_hex[2:]
            
            if len(signature_hex) != 130:
                logger.warning(f"Invalid signature length: {len(signature_hex)}")
                return None
            
            # Extract components
            r = int(signature_hex[:64], 16)
            s = int(signature_hex[64:128], 16)
            v = int(signature_hex[128:130], 16)
            
            # Recover public key
            sig = keys.Signature(vrs=(v, r, s))
            public_key = keys.PublicKey.recover_from_msg_hash(tx_hash, sig)
            address = public_key.to_checksum_address()
            
            logger.info(f"Recovered sender: {address}")
            return address
        except Exception as e:
            logger.error(f"Failed to recover sender: {str(e)}")
            return None


class FacilitatorService:
    """Main payment facilitator service supporting multiple networks."""

    def __init__(
        self,
        cronos_rpc_url: str,
        cronos_pay_to: str,
        cronos_asset: str,
        cronos_chain_id: int,
    ):
        """Initialize facilitator with network configurations.
        
        Args:
            cronos_rpc_url: Cronos RPC endpoint URL
            cronos_pay_to: Cronos recipient address (0x...)
            cronos_asset: Asset symbol or ERC20 contract address
            cronos_chain_id: Cronos chain ID (25 for mainnet, 338 for testnet)
        """
        self.cronos_verifier = CronosPaymentVerifier(cronos_rpc_url)
        self.cronos_pay_to = cronos_pay_to
        self.cronos_asset = cronos_asset
        self.cronos_chain_id = cronos_chain_id

    def verify_payment(
        self,
        network: str,
        asset: str,
        amount: int,
        raw_tx: str,
        signature: str,
    ) -> PaymentVerificationResult:
        """Verify a payment across supported networks.
        
        Args:
            network: "cronos" or "movement"
            asset: Asset symbol (CRO) or contract address (0x...)
            amount: Amount in smallest unit
            raw_tx: Raw transaction hex
            signature: Transaction signature
            
        Returns:
            PaymentVerificationResult
        """
        if network == NetworkType.CRONOS.value:
            requirements = PaymentRequirements(
                network=NetworkType.CRONOS,
                asset=asset,
                amount=amount,
                pay_to=self.cronos_pay_to,
                chain_id=self.cronos_chain_id,
            )
            return self.cronos_verifier.verify_payment(
                requirements, raw_tx, signature
            )
        else:
            return PaymentVerificationResult(
                is_valid=False,
                tx_hash="",
                network=network,
                from_address="",
                to_address="",
                amount="0",
                asset="",
                error_message=f"Unsupported network: {network}",
            )

    def settle_payment(
        self,
        network: str,
        raw_tx: str,
    ) -> Dict[str, Any]:
        """Settle a verified payment.
        
        Args:
            network: "cronos" or "movement"
            raw_tx: Raw transaction hex
            
        Returns:
            Settlement result with tx_hash and status
        """
        if network == NetworkType.CRONOS.value:
            return self.cronos_verifier.settle_payment(raw_tx)
        else:
            return {
                "tx_hash": "",
                "network": network,
                "status": "failed",
                "error": f"Unsupported network: {network}",
            }

    def get_supported_networks(self) -> Dict[str, Any]:
        """Get information about supported networks and assets.
        
        Returns:
            Dictionary with supported networks and their configuration
        """
        return {
            "supported_networks": [
                {
                    "network": "cronos",
                    "chain_id": self.cronos_chain_id,
                    "asset": self.cronos_asset,
                    "pay_to": self.cronos_pay_to,
                }
            ]
        }
