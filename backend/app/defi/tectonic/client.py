"""
TectonicClient: thin Web3 wrapper for core Tectonic money market operations.

Focus in this phase:
- Connection & account handling
- Contract bindings (USDC, tUSDC, Comptroller)
- High-level methods for: supply (mint), enter markets, borrow, repay, redeem

This module is backend-only and does NOT handle user prompts or agent logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.types import TxParams, TxReceipt

from .config import TECTONIC_ADDRESSES, TECTONIC_NETWORK


# --- Minimal ABIs -----------------------------------------------------------------

ERC20_ABI: List[Dict] = [
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


CTOKEN_ABI: List[Dict] = [
    # Core money market methods
    {
        "constant": False,
        "inputs": [{"name": "mintAmount", "type": "uint256"}],
        "name": "mint",
        "outputs": [{"name": "error", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "redeemTokens", "type": "uint256"}],
        "name": "redeem",
        "outputs": [{"name": "error", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "redeemAmount", "type": "uint256"}],
        "name": "redeemUnderlying",
        "outputs": [{"name": "error", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "borrowAmount", "type": "uint256"}],
        "name": "borrow",
        "outputs": [{"name": "error", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "repayAmount", "type": "uint256"}],
        "name": "repayBorrow",
        "outputs": [{"name": "error", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "borrowBalanceCurrent",
        "outputs": [{"name": "borrowBalance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "underlying",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "comptroller",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
    },
    # Cronos Tectonic uses `tectonicCore()` instead of `comptroller()` on some markets.
    {
        "constant": True,
        "inputs": [],
        "name": "tectonicCore",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


COMPTROLLER_ABI: List[Dict] = [
    {
        "constant": False,
        "inputs": [{"name": "cTokens", "type": "address[]"}],
        "name": "enterMarkets",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "getAssetsIn",
        "outputs": [{"name": "", "type": "address[]"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "getAccountLiquidity",
        "outputs": [
            {"name": "error", "type": "uint256"},
            {"name": "liquidity", "type": "uint256"},
            {"name": "shortfall", "type": "uint256"},
        ],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "cToken", "type": "address"}],
        "name": "markets",
        "outputs": [
            {"name": "isListed", "type": "bool"},
            {"name": "collateralFactorMantissa", "type": "uint256"},
            {"name": "isComped", "type": "bool"},
        ],
        "type": "function",
    },
]


# --- Exceptions / types -----------------------------------------------------------


class TectonicError(Exception):
    """Base exception for Tectonic integration."""


class TectonicOperationError(TectonicError):
    """Raised when a protocol call returns a non-zero error code."""

    def __init__(self, operation: str, code: int):
        super().__init__(f"Tectonic operation '{operation}' failed with error code {code}")
        self.operation = operation
        self.code = code


@dataclass
class AccountLiquidity:
    error: int
    liquidity: int
    shortfall: int


# --- Client -----------------------------------------------------------------------


class TectonicClient:
    """
    Thin client around Tectonic USDC market on Cronos.

    For now this focuses on:
    - USDC <-> tUSDC
    - Core lending lifecycle (supply, enter markets, borrow, repay, redeem)
    """

    def __init__(self, rpc_url: Optional[str] = None, private_key: Optional[str] = None) -> None:
        # Resolve RPC
        env_rpc = os.getenv("CRONOS_RPC")
        self.rpc_url = rpc_url or env_rpc or (TECTONIC_NETWORK.rpc_urls[0] if TECTONIC_NETWORK.rpc_urls else None)
        if not self.rpc_url:
            raise TectonicError("No Cronos RPC URL available for TectonicClient.")

        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 10}))
        self.web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not self.web3.is_connected():
            raise TectonicError(f"Failed to connect to Cronos RPC: {self.rpc_url}")

        chain_id = self.web3.eth.chain_id
        if chain_id != TECTONIC_NETWORK.chain_id:
            raise TectonicError(f"Connected to wrong chain_id={chain_id}, expected {TECTONIC_NETWORK.chain_id}.")

        self.chain_id = chain_id

        # Optional signing account (for write operations)
        self._private_key = None
        self.address: Optional[str] = None
        if private_key:
            if not private_key.startswith("0x"):
                private_key = "0x" + private_key
            account = self.web3.eth.account.from_key(private_key)
            self._private_key = private_key
            self.address = account.address

        # Contracts
        self.usdc = self.web3.eth.contract(
            address=self.web3.to_checksum_address(TECTONIC_ADDRESSES.usdc),
            abi=ERC20_ABI,
        )
        self.tusdc = self.web3.eth.contract(
            address=self.web3.to_checksum_address(TECTONIC_ADDRESSES.tusdc),
            abi=CTOKEN_ABI,
        )

        # Resolve the correct "risk engine" address for this market.
        # On Cronos Tectonic, this is often exposed as `tectonicCore()` on the tToken.
        self.core_address = self._resolve_core_address()
        self.comptroller = self.web3.eth.contract(address=self.core_address, abi=COMPTROLLER_ABI)

    def _resolve_core_address(self) -> str:
        """
        Determine the correct core/proxy address for enterMarkets/liquidity.

        Preference order:
        - tUSDC.tectonicCore() if available (Cronos Tectonic)
        - tUSDC.comptroller() if available (Compound-like)
        - fallback to configured address
        """
        # Try tectonicCore()
        try:
            core = self.tusdc.functions.tectonicCore().call()
            if core and int(core, 16) != 0:
                return self.web3.to_checksum_address(core)
        except Exception:
            pass

        # Try comptroller()
        try:
            comp = self.tusdc.functions.comptroller().call()
            if comp and int(comp, 16) != 0:
                return self.web3.to_checksum_address(comp)
        except Exception:
            pass

        return self.web3.to_checksum_address(TECTONIC_ADDRESSES.comptroller)

    # --- Internal helpers --------------------------------------------------------

    def _require_signer(self) -> str:
        if not self.address or not self._private_key:
            raise TectonicError("TectonicClient was created without a private key; write operation not allowed.")
        return self.address

    def _build_and_send(self, func, tx_overrides: Optional[TxParams] = None) -> TxReceipt:
        """
        Build, sign and send a transaction for the given contract function.
        Uses simple gasPrice-based strategy for now.
        """
        sender = self._require_signer()
        base: TxParams = {
            "from": sender,
            "nonce": self.web3.eth.get_transaction_count(sender),
            "chainId": self.chain_id,
        }
        if tx_overrides:
            base.update(tx_overrides)

        # Estimate gas with small buffer
        try:
            gas_estimate = func.estimate_gas(base)
        except Exception:
            gas_estimate = 400_000

        base.setdefault("gas", int(gas_estimate * 1.2))
        base.setdefault("gasPrice", self.web3.eth.gas_price)

        tx = func.build_transaction(base)
        signed = self.web3.eth.account.sign_transaction(tx, private_key=self._private_key)
        raw_tx = getattr(signed, "raw_transaction", getattr(signed, "rawTransaction", None))
        tx_hash = self.web3.eth.send_raw_transaction(raw_tx)
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise TectonicError(f"Transaction reverted; tx_hash={tx_hash.hex()}")
        return receipt

    # --- Read methods -----------------------------------------------------------

    def get_account_liquidity(self, address: Optional[str] = None) -> AccountLiquidity:
        """Return (error, liquidity, shortfall) for account from Comptroller."""
        addr = self.web3.to_checksum_address(address or self._require_signer())
        error, liquidity, shortfall = self.comptroller.functions.getAccountLiquidity(addr).call()
        return AccountLiquidity(error=int(error), liquidity=int(liquidity), shortfall=int(shortfall))

    def get_assets_in(self, address: Optional[str] = None) -> List[str]:
        """Return list of tToken addresses entered as collateral."""
        addr = self.web3.to_checksum_address(address or self._require_signer())
        return list(self.comptroller.functions.getAssetsIn(addr).call())

    def get_borrow_balance(self, address: Optional[str] = None) -> int:
        """Return up-to-date borrow balance for tUSDC (includes accrued interest)."""
        addr = self.web3.to_checksum_address(address or self._require_signer())
        return int(self.tusdc.functions.borrowBalanceCurrent(addr).call())

    def get_tusdc_balance(self, address: Optional[str] = None) -> int:
        addr = self.web3.to_checksum_address(address or self._require_signer())
        return int(self.tusdc.functions.balanceOf(addr).call())

    def get_usdc_balance(self, address: Optional[str] = None) -> int:
        addr = self.web3.to_checksum_address(address or self._require_signer())
        return int(self.usdc.functions.balanceOf(addr).call())

    # --- Allowance / collateral management --------------------------------------

    def ensure_usdc_allowance(self, required_amount: int, spender: Optional[str] = None) -> None:
        """
        Ensure allowance from user -> tUSDC is at least required_amount.
        For safety, we approve exactly required_amount (not infinite).
        """
        owner = self.web3.to_checksum_address(self._require_signer())
        spender_addr = self.web3.to_checksum_address(spender or TECTONIC_ADDRESSES.tusdc)
        current = int(self.usdc.functions.allowance(owner, spender_addr).call())
        if current >= required_amount:
            return

        func = self.usdc.functions.approve(spender_addr, required_amount)
        self._build_and_send(func)

    def enter_markets_if_needed(self, markets: Optional[Sequence[str]] = None) -> None:
        """
        Call Comptroller.enterMarkets for any markets the user hasn't entered yet.
        By default, only ensures tUSDC is entered.
        """
        user = self.web3.to_checksum_address(self._require_signer())
        existing = set(self.comptroller.functions.getAssetsIn(user).call())

        targets: List[str] = []
        if markets:
            for m in markets:
                cm = self.web3.to_checksum_address(m)
                if cm not in existing:
                    targets.append(cm)
        else:
            tusdc_addr = self.web3.to_checksum_address(TECTONIC_ADDRESSES.tusdc)
            if tusdc_addr not in existing:
                targets.append(tusdc_addr)

        if not targets:
            return

        func = self.comptroller.functions.enterMarkets(targets)
        receipt = self._build_and_send(func)
        # Decode return values with a call (enterMarkets is non-view but returns codes)
        # Safer: re-call with eth_call to inspect error codes
        error_codes = self.comptroller.functions.enterMarkets(targets).call({"from": user})
        for idx, code in enumerate(error_codes):
            if int(code) != 0:
                raise TectonicOperationError(f"enterMarkets[{idx}]", int(code))
        _ = receipt  # to silence linters if unused later

    # --- Core workflows ---------------------------------------------------------

    def supply_usdc(self, amount_wei: int) -> TxReceipt:
        """
        Supply USDC to Tectonic (mint tUSDC).
        Steps:
        - ensure allowance from user -> tUSDC
        - call tUSDC.mint(amount)
        - check return error code via eth_call, assume tx success on-chain
        """
        self.ensure_usdc_allowance(required_amount=amount_wei)
        func = self.tusdc.functions.mint(amount_wei)

        # Pre-flight: check error code via static call
        error_code = int(func.call({"from": self._require_signer()}))
        if error_code != 0:
            raise TectonicOperationError("mint", error_code)

        return self._build_and_send(func)

    def borrow_usdc(self, amount_wei: int) -> TxReceipt:
        """
        Borrow USDC from Tectonic (against enabled collateral).
        Responsibility for safe LTV / health factor checks lives
        in a higher-level risk engine; here we just perform the borrow.
        """
        func = self.tusdc.functions.borrow(amount_wei)
        error_code = int(func.call({"from": self._require_signer()}))
        if error_code != 0:
            raise TectonicOperationError("borrow", error_code)
        return self._build_and_send(func)

    def repay_usdc(self, amount_wei: int) -> TxReceipt:
        """
        Repay a USDC borrow.
        Caller is responsible for passing either:
        - a specific amount (may leave small dust), or
        - MAX_UINT256 if later we confirm "repay all" semantics are supported.
        """
        self.ensure_usdc_allowance(required_amount=amount_wei, spender=TECTONIC_ADDRESSES.tusdc)
        func = self.tusdc.functions.repayBorrow(amount_wei)
        error_code = int(func.call({"from": self._require_signer()}))
        if error_code != 0:
            raise TectonicOperationError("repayBorrow", error_code)
        return self._build_and_send(func)

    def redeem_tusdc(self, ttoken_amount: int) -> TxReceipt:
        """Redeem a given amount of tUSDC tokens back to USDC."""
        func = self.tusdc.functions.redeem(ttoken_amount)
        error_code = int(func.call({"from": self._require_signer()}))
        if error_code != 0:
            raise TectonicOperationError("redeem", error_code)
        return self._build_and_send(func)

    def redeem_usdc(self, underlying_amount: int) -> TxReceipt:
        """Redeem a specific amount of underlying USDC."""
        func = self.tusdc.functions.redeemUnderlying(underlying_amount)
        error_code = int(func.call({"from": self._require_signer()}))
        if error_code != 0:
            raise TectonicOperationError("redeemUnderlying", error_code)
        return self._build_and_send(func)


