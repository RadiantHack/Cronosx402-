"""
Balance API Helper

Provides a structured JSON endpoint for fetching balance data
without the agent's text formatting.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .agent import fetch_cronos_balances, validate_address

router = APIRouter()


class BalanceRequest(BaseModel):
    """Request model for balance queries"""
    address: str
    network: str = "cronos"


class BalanceResponse(BaseModel):
    """Response model for balance data"""
    address: str
    balances: list
    success: bool
    error: str | None = None
    total_fetched: int | None = None
    filtered_out: int | None = None


@router.post("/api/balance/json")
async def get_balance_json(request: BalanceRequest) -> Dict[str, Any]:
    """
    Get structured balance data without agent text formatting.
    
    This endpoint directly calls fetch_cronos_balances and returns
    the raw JSON data structure.
    """
    # Validate address
    if not validate_address(request.address):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid address format: {request.address}"
        )
    
    # Only Cronos is supported for now
    if request.network.lower() != "cronos":
        raise HTTPException(
            status_code=400,
            detail=f"Network '{request.network}' not supported. Only 'cronos' is available."
        )
    
    # Fetch balance data
    try:
        balance_data = fetch_cronos_balances(request.address)
        return balance_data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching balance: {str(e)}"
        )
