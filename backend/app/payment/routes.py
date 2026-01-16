"""
Payment API Routes for x402 Paytech.

Endpoints for payment verification, settlement, and network support information.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.payment.facilitator import FacilitatorService
from app.payment.config import cronos_config

router = APIRouter(prefix="/facilitator", tags=["payment"])

# Initialize facilitator service
try:
    cronos_config.validate()
    facilitator_service = FacilitatorService(
        cronos_rpc_url=cronos_config.cronos_rpc_url,
        cronos_pay_to=cronos_config.cronos_pay_to,
        cronos_asset=cronos_config.cronos_asset,
        cronos_chain_id=cronos_config.cronos_chain_id,
    )
except ValueError as e:
    facilitator_service = None
    print(f"⚠️  Cronos payment config validation failed: {e}")


class PaymentVerificationRequest(BaseModel):
    """Request body for payment verification."""
    network: str
    asset: str
    amount: int
    raw_transaction: str
    signature: str


class PaymentSettlementRequest(BaseModel):
    """Request body for payment settlement."""
    network: str
    raw_transaction: str


class VerifyPaymentResponse(BaseModel):
    """Response from payment verification."""
    is_valid: bool
    tx_hash: str
    network: str
    from_address: str
    to_address: str
    amount: str
    asset: str
    error_message: Optional[str] = None


class SettlePaymentResponse(BaseModel):
    """Response from payment settlement."""
    tx_hash: str
    network: str
    status: str
    error: Optional[str] = None


@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(request: PaymentVerificationRequest) -> VerifyPaymentResponse:
    """Verify a payment transaction against requirements.
    
    Args:
        request: Payment verification request with transaction details
        
    Returns:
        Verification result with transaction hash and validity status
        
    Raises:
        HTTPException: If facilitator service is not configured
    """
    if not facilitator_service:
        raise HTTPException(
            status_code=503,
            detail="Payment facilitator service not configured"
        )
    
    result = facilitator_service.verify_payment(
        network=request.network,
        asset=request.asset,
        amount=request.amount,
        raw_tx=request.raw_transaction,
        signature=request.signature,
    )
    
    return VerifyPaymentResponse(**result.__dict__)


@router.post("/settle", response_model=SettlePaymentResponse)
async def settle_payment(request: PaymentSettlementRequest) -> SettlePaymentResponse:
    """Settle (submit) a verified payment transaction.
    
    Args:
        request: Settlement request with verified transaction
        
    Returns:
        Settlement result with transaction hash and status
        
    Raises:
        HTTPException: If facilitator service is not configured
    """
    if not facilitator_service:
        raise HTTPException(
            status_code=503,
            detail="Payment facilitator service not configured"
        )
    
    result = facilitator_service.settle_payment(
        network=request.network,
        raw_tx=request.raw_transaction,
    )
    
    return SettlePaymentResponse(**result)


@router.get("/supported")
async def get_supported_networks():
    """Get list of supported payment networks and their configuration.
    
    Returns:
        Dictionary with supported networks and their settings
        
    Raises:
        HTTPException: If facilitator service is not configured
    """
    if not facilitator_service:
        raise HTTPException(
            status_code=503,
            detail="Payment facilitator service not configured"
        )
    
    return facilitator_service.get_supported_networks()
