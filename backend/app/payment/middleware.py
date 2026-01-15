"""
Payment Verification Middleware for x402 Paytech.

Middleware that intercepts requests to paywalled routes and verifies payment before allowing access.
"""

from typing import Optional, Callable, Any, Dict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.payment.facilitator import FacilitatorService


class PaymentVerificationMiddleware(BaseHTTPMiddleware):
    """Middleware to verify payments before allowing access to protected routes."""

    def __init__(
        self,
        app,
        facilitator_service: FacilitatorService,
        paywalled_routes: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """Initialize payment middleware.
        
        Args:
            app: The ASGI application
            facilitator_service: FacilitatorService instance for payment verification
            paywalled_routes: Dict mapping route paths to payment requirements.
                Format: {
                    "/agent/route": {
                        "network": "cronos",
                        "asset": "CRO" or "0x...",
                        "amount": 1000000000,  # in smallest unit
                    }
                }
        """
        super().__init__(app)
        self.facilitator_service = facilitator_service
        self.paywalled_routes = paywalled_routes or {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and verify payment if route requires it.
        
        Args:
            request: The incoming request
            call_next: The next middleware/handler
            
        Returns:
            Response from the next handler or payment verification error
        """
        # Check if route requires payment
        route_config = self._get_route_config(request.url.path)
        if not route_config:
            # Route is not paywalled
            return await call_next(request)

        # Extract payment header
        payment_header = request.headers.get("x-payment")
        if not payment_header:
            raise HTTPException(
                status_code=402,
                detail="Payment required. Please provide x-payment header.",
            )

        # Parse payment header (format: network:asset:amount:raw_tx:signature)
        try:
            parts = payment_header.split(":")
            if len(parts) < 5:
                raise ValueError("Invalid payment header format")
            
            network, asset, amount_str = parts[0], parts[1], parts[2]
            raw_tx = ":".join(parts[3:-1])  # Handle signatures with colons
            signature = parts[-1]
            
            amount = int(amount_str)
        except (ValueError, IndexError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid payment header: {str(e)}",
            )

        # Verify payment
        verification_result = self.facilitator_service.verify_payment(
            network=network,
            asset=asset,
            amount=amount,
            raw_tx=raw_tx,
            signature=signature,
        )

        if not verification_result.is_valid:
            raise HTTPException(
                status_code=402,
                detail=f"Payment verification failed: {verification_result.error_message}",
            )

        # Optionally settle the payment
        settlement_result = self.facilitator_service.settle_payment(
            network=network,
            raw_tx=raw_tx,
        )

        # Proceed to next handler and attach payment info to request
        request.state.payment = {
            "verified": True,
            "network": verification_result.network,
            "tx_hash": verification_result.tx_hash,
            "from_address": verification_result.from_address,
            "amount": verification_result.amount,
            "settlement": settlement_result,
        }

        response = await call_next(request)
        
        # Add payment response header
        if settlement_result.get("status") == "submitted":
            response.headers["x-payment-response"] = f"settled:{settlement_result['tx_hash']}"
        
        return response

    def _get_route_config(self, path: str) -> Optional[Dict[str, Any]]:
        """Get payment config for a route path.
        
        Args:
            path: Request path
            
        Returns:
            Payment configuration or None if route is not paywalled
        """
        # Exact match
        if path in self.paywalled_routes:
            return self.paywalled_routes[path]
        
        # Prefix match (e.g., /agent/balance matches /agent/balance/something)
        for route, config in self.paywalled_routes.items():
            if path.startswith(route):
                return config
        
        return None


def create_payment_middleware(
    facilitator_service: FacilitatorService,
    paywalled_routes: Optional[Dict[str, Dict[str, Any]]] = None,
):
    """Factory function to create payment middleware.
    
    Args:
        facilitator_service: FacilitatorService instance
        paywalled_routes: Routes that require payment
        
    Returns:
        Middleware class configured with payment requirements
    """
    def middleware(app):
        return PaymentVerificationMiddleware(app, facilitator_service, paywalled_routes)
    
    return middleware
