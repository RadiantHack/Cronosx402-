"""
Tectonic A2A API Endpoints

RESTful API surface for integrating Tectonic lending operations.

Endpoints:
- POST /tectonic/supply - Supply USDC & enable collateral
- POST /tectonic/borrow - Borrow USDC (with HF checks)
- POST /tectonic/repay - Repay borrow
- POST /tectonic/withdraw - Withdraw supplied USDC
- GET /tectonic/position - Fetch position info (HF, supplied, borrowed, etc.)
- GET /tectonic/config - Get Tectonic config info
"""

from decimal import Decimal
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from ..defi.tectonic.client import TectonicClient
from ..defi.tectonic.risk_engine import RiskEngine
from .service import (
    TectonicService,
    SupplyRequest,
    BorrowRequest,
    RepayRequest,
    WithdrawRequest,
    PositionInfo,
    OperationResult,
)

router = APIRouter(prefix="/tectonic", tags=["tectonic"])


# --- Request/Response Models ---

class SupplyRequestModel(BaseModel):
    """API request for supply operation."""
    address: str = Field(..., description="User wallet address")
    amount_usdc: float = Field(..., description="Amount of USDC to supply")
    use_as_collateral: bool = Field(default=True, description="Enable collateral use")
    private_key: Optional[str] = Field(None, description="Private key for signing (optional if session-based)")


class BorrowRequestModel(BaseModel):
    """API request for borrow operation."""
    address: str = Field(..., description="User wallet address")
    amount_usdc: float = Field(..., description="Amount of USDC to borrow")
    check_health_factor: bool = Field(default=True, description="Verify HF >= 1.2")
    private_key: Optional[str] = Field(None, description="Private key for signing")


class RepayRequestModel(BaseModel):
    """API request for repay operation."""
    address: str = Field(..., description="User wallet address")
    amount_usdc: Optional[float] = Field(None, description="Amount to repay; None = repay all")
    private_key: Optional[str] = Field(None, description="Private key for signing")


class WithdrawRequestModel(BaseModel):
    """API request for withdraw operation."""
    address: str = Field(..., description="User wallet address")
    amount_usdc: Optional[float] = Field(None, description="Amount to withdraw; None = withdraw all")
    private_key: Optional[str] = Field(None, description="Private key for signing")


class PositionResponseModel(BaseModel):
    """Response with position info."""
    success: bool
    position: Optional[Dict] = None
    error: Optional[str] = None


class OperationResponseModel(BaseModel):
    """Response from supply/borrow/repay/withdraw operations."""
    success: bool
    tx_hash: Optional[str] = None
    gas_used: Optional[int] = None
    position_after: Optional[Dict] = None
    error: Optional[str] = None


# --- Service Initialization ---

def get_service_for_request(request_data: Dict, private_key: Optional[str] = None) -> TectonicService:
    """Create a TectonicService instance for the request."""
    # Use provided private key or fetch from request
    pk = private_key or request_data.get("private_key")
    if not pk:
        raise HTTPException(
            status_code=400,
            detail="private_key is required"
        )
    
    # Create client
    client = TectonicClient(private_key=pk)
    
    # Create risk engine
    risk_engine = RiskEngine(client, safety_ltv=Decimal("0.75"))
    
    # Create service
    return TectonicService(client, risk_engine=risk_engine)


def position_to_dict(pos: PositionInfo) -> Dict:
    """Convert PositionInfo to serializable dict."""
    return {
        "supplied_usdc": float(pos.supplied_usdc),
        "supplied_tusd_tokens": float(pos.supplied_tusd_tokens),
        "borrowed_usdc": float(pos.borrowed_usdc),
        "available_liquidity_usdc": float(pos.available_liquidity_usdc),
        "health_factor": float(pos.health_factor) if pos.health_factor else None,
        "health_status": pos.health_status,
        "safe_borrow_limit_usdc": float(pos.safe_borrow_limit_usdc),
        "liquidation_buffer_usdc": float(pos.liquidation_buffer_usdc),
        "is_collateral_enabled": pos.is_collateral_enabled,
    }


# --- Endpoints ---

@router.post("/supply", response_model=OperationResponseModel)
async def supply(request: SupplyRequestModel) -> OperationResponseModel:
    """
    Supply USDC to Tectonic and optionally enable as collateral.
    
    **Request:**
    - `address`: User wallet address
    - `amount_usdc`: Amount of USDC to supply
    - `use_as_collateral`: Whether to enable collateral (default: true)
    - `private_key`: Private key for transaction signing
    
    **Response:**
    - `success`: Whether operation succeeded
    - `tx_hash`: Transaction hash if successful
    - `gas_used`: Gas consumed
    - `position_after`: Updated position info
    - `error`: Error message if failed
    """
    try:
        service = get_service_for_request(request.dict(), request.private_key)
        
        # Validate address format
        if not request.address.startswith("0x") or len(request.address) != 42:
            raise HTTPException(status_code=400, detail="Invalid address format")
        
        # Create supply request
        supply_req = SupplyRequest(
            amount_usdc=Decimal(str(request.amount_usdc)),
            use_as_collateral=request.use_as_collateral,
        )
        
        # Execute supply
        result = service.supply(supply_req, address=request.address)
        
        return OperationResponseModel(
            success=result.success,
            tx_hash=result.tx_hash,
            gas_used=result.gas_used,
            position_after=position_to_dict(result.position_after) if result.position_after else None,
            error=result.error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        return OperationResponseModel(
            success=False,
            error=f"Supply operation failed: {str(e)}",
        )


@router.post("/borrow", response_model=OperationResponseModel)
async def borrow(request: BorrowRequestModel) -> OperationResponseModel:
    """
    Borrow USDC from Tectonic with health factor checks.
    
    **Request:**
    - `address`: User wallet address
    - `amount_usdc`: Amount of USDC to borrow
    - `check_health_factor`: Verify HF >= 1.2 (default: true)
    - `private_key`: Private key for transaction signing
    
    **Response:**
    - `success`: Whether operation succeeded
    - `tx_hash`: Transaction hash if successful
    - `gas_used`: Gas consumed
    - `position_after`: Updated position info with new HF
    - `error`: Error message if failed (e.g., HF too low)
    """
    try:
        service = get_service_for_request(request.dict(), request.private_key)
        
        # Validate address format
        if not request.address.startswith("0x") or len(request.address) != 42:
            raise HTTPException(status_code=400, detail="Invalid address format")
        
        # Create borrow request
        borrow_req = BorrowRequest(
            amount_usdc=Decimal(str(request.amount_usdc)),
            check_health_factor=request.check_health_factor,
        )
        
        # Execute borrow
        result = service.borrow(borrow_req, address=request.address)
        
        return OperationResponseModel(
            success=result.success,
            tx_hash=result.tx_hash,
            gas_used=result.gas_used,
            position_after=position_to_dict(result.position_after) if result.position_after else None,
            error=result.error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        return OperationResponseModel(
            success=False,
            error=f"Borrow operation failed: {str(e)}",
        )


@router.post("/repay", response_model=OperationResponseModel)
async def repay(request: RepayRequestModel) -> OperationResponseModel:
    """
    Repay USDC borrow.
    
    **Request:**
    - `address`: User wallet address
    - `amount_usdc`: Amount to repay (optional; omit to repay all)
    - `private_key`: Private key for transaction signing
    
    **Response:**
    - `success`: Whether operation succeeded
    - `tx_hash`: Transaction hash if successful
    - `gas_used`: Gas consumed
    - `position_after`: Updated position info with repayment applied
    - `error`: Error message if failed
    """
    try:
        service = get_service_for_request(request.dict(), request.private_key)
        
        # Validate address format
        if not request.address.startswith("0x") or len(request.address) != 42:
            raise HTTPException(status_code=400, detail="Invalid address format")
        
        # Create repay request
        repay_req = RepayRequest(
            amount_usdc=Decimal(str(request.amount_usdc)) if request.amount_usdc else None,
        )
        
        # Execute repay
        result = service.repay(repay_req, address=request.address)
        
        return OperationResponseModel(
            success=result.success,
            tx_hash=result.tx_hash,
            gas_used=result.gas_used,
            position_after=position_to_dict(result.position_after) if result.position_after else None,
            error=result.error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        return OperationResponseModel(
            success=False,
            error=f"Repay operation failed: {str(e)}",
        )


@router.post("/withdraw", response_model=OperationResponseModel)
async def withdraw(request: WithdrawRequestModel) -> OperationResponseModel:
    """
    Withdraw USDC from supply (redeem tUSDC) with liquidation warnings.
    
    **Request:**
    - `address`: User wallet address
    - `amount_usdc`: Amount to withdraw (optional; omit to withdraw all available)
    - `private_key`: Private key for transaction signing
    
    **Response:**
    - `success`: Whether operation succeeded
    - `tx_hash`: Transaction hash if successful
    - `gas_used`: Gas consumed
    - `position_after`: Updated position info with withdrawal applied
    - `error`: Error message if failed (e.g., would cause liquidation)
    """
    try:
        service = get_service_for_request(request.dict(), request.private_key)
        
        # Validate address format
        if not request.address.startswith("0x") or len(request.address) != 42:
            raise HTTPException(status_code=400, detail="Invalid address format")
        
        # Create withdraw request
        withdraw_req = WithdrawRequest(
            amount_usdc=Decimal(str(request.amount_usdc)) if request.amount_usdc else None,
        )
        
        # Execute withdraw
        result = service.withdraw(withdraw_req, address=request.address)
        
        return OperationResponseModel(
            success=result.success,
            tx_hash=result.tx_hash,
            gas_used=result.gas_used,
            position_after=position_to_dict(result.position_after) if result.position_after else None,
            error=result.error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        return OperationResponseModel(
            success=False,
            error=f"Withdraw operation failed: {str(e)}",
        )


@router.get("/position", response_model=PositionResponseModel)
async def get_position(address: str) -> PositionResponseModel:
    """
    Get current position info for a user.
    
    **Query Parameters:**
    - `address`: User wallet address
    
    **Response:**
    - `success`: Whether query succeeded
    - `position`: Position details (supplied, borrowed, HF, etc.)
    - `error`: Error message if failed
    
    **Position Fields:**
    - `supplied_usdc`: Total USD value of supplied collateral
    - `borrowed_usdc`: Total USD value of borrows
    - `health_factor`: Health factor (HF); HF < 1.0 = liquidatable
    - `health_status`: "healthy" / "warning" / "critical" / "liquidatable"
    - `safe_borrow_limit_usdc`: Max safe borrow amount (with 1.2x HF buffer)
    - `liquidation_buffer_usdc`: Distance to liquidation (in USD)
    - `is_collateral_enabled`: Whether tUSDC is enabled as collateral
    """
    try:
        # Validate address format
        if not address.startswith("0x") or len(address) != 42:
            raise HTTPException(status_code=400, detail="Invalid address format")
        
        # Create a read-only client (no private key needed for query)
        client = TectonicClient()
        client.address = address  # Set account address for read-only queries
        risk_engine = RiskEngine(client, safety_ltv=Decimal("0.75"))
        service = TectonicService(client, risk_engine=risk_engine)

        # Get position
        position = service.get_position(address)

        return PositionResponseModel(
            success=True,
            position=position_to_dict(position),
        )
    except HTTPException:
        raise
    except Exception as e:
        return PositionResponseModel(
            success=False,
            error=f"Failed to fetch position: {str(e)}",
        )


@router.get("/config")
async def get_config() -> Dict:
    """
    Get Tectonic configuration and contract addresses.
    
    **Response:**
    - `network`: Network config (name, chain_id, RPC URLs)
    - `addresses`: Contract addresses (TONIC, USDC, tUSDC, Comptroller)
    """
    from ..defi.tectonic.config import as_dict
    
    return as_dict()
