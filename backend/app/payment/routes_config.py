"""
Route Configuration System for Agent Paywalling.

Defines route configurations for agents with optional payment requirements.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class RouteConfig:
    """Configuration for an agent route with optional payment requirements."""
    
    # Route identity
    path: str
    method: str = "POST"
    
    # Payment requirements (optional - route is free if not specified)
    network: Optional[str] = None  # "cronos", "movement", etc.
    asset: Optional[str] = None  # "CRO", "APT", or ERC20 address "0x..."
    amount: Optional[int] = None  # Amount in smallest unit (wei, octa, etc.)
    
    # Agent info
    agent_name: Optional[str] = None
    description: Optional[str] = None

    def is_paywalled(self) -> bool:
        """Check if this route requires payment."""
        return self.network is not None and self.asset is not None and self.amount is not None

    def get_payment_config(self) -> Dict[str, Any]:
        """Get payment configuration for middleware.
        
        Returns:
            Dict with network, asset, and amount if paywalled, else empty dict
        """
        if not self.is_paywalled():
            return {}
        
        return {
            "network": self.network,
            "asset": self.asset,
            "amount": self.amount,
        }


class RouteRegistry:
    """Registry of all agent routes and their payment configurations."""
    
    def __init__(self):
        """Initialize empty registry."""
        self._routes: Dict[str, RouteConfig] = {}

    def register(self, config: RouteConfig) -> None:
        """Register a route configuration.
        
        Args:
            config: RouteConfig instance
        """
        key = f"{config.method} {config.path}"
        self._routes[key] = config

    def register_batch(self, configs: List[RouteConfig]) -> None:
        """Register multiple route configurations.
        
        Args:
            configs: List of RouteConfig instances
        """
        for config in configs:
            self.register(config)

    def get(self, path: str, method: str = "POST") -> Optional[RouteConfig]:
        """Get route configuration.
        
        Args:
            path: Route path
            method: HTTP method (default: POST)
            
        Returns:
            RouteConfig or None if not found
        """
        key = f"{method} {path}"
        return self._routes.get(key)

    def get_paywalled_routes(self) -> Dict[str, Dict[str, Any]]:
        """Get all paywalled routes in middleware format.
        
        Returns:
            Dict mapping paths to payment configs
        """
        result = {}
        for route_config in self._routes.values():
            if route_config.is_paywalled():
                result[route_config.path] = route_config.get_payment_config()
        return result

    def list_all(self) -> List[RouteConfig]:
        """Get all registered routes.
        
        Returns:
            List of RouteConfig instances
        """
        return list(self._routes.values())

    def list_paywalled(self) -> List[RouteConfig]:
        """Get all paywalled routes.
        
        Returns:
            List of RouteConfig instances that require payment
        """
        return [rc for rc in self._routes.values() if rc.is_paywalled()]


# Global route registry
route_registry = RouteRegistry()


# Example route configurations for agents
# These can be imported and used in your agent initialization

BALANCE_AGENT_ROUTES = [
    RouteConfig(
        path="/balance",
        method="POST",
        network="cronos",
        asset="CRO",
        amount=int(0.1 * 1e18),  # 0.1 CRO
        agent_name="Balance Agent",
        description="Check cryptocurrency balances",
    ),
]

TRANSFER_AGENT_ROUTES = [
    RouteConfig(
        path="/transfer",
        method="POST",
        network="cronos",
        asset="CRO",
        amount=int(0.5 * 1e18),  # 0.5 CRO for transfer operations
        agent_name="Transfer Agent",
        description="Transfer native CRO tokens",
    ),
]

SWAP_AGENT_ROUTES = [
    RouteConfig(
        path="/swap",
        method="POST",
        network="cronos",
        asset="CRO",
        amount=int(0.2 * 1e18),  # 0.2 CRO for swap operations
        agent_name="Swap Agent",
        description="Swap tokens on DEX",
    ),
]

BRIDGE_AGENT_ROUTES = [
    RouteConfig(
        path="/bridge",
        method="POST",
        network="cronos",
        asset="CRO",
        amount=int(1.0 * 1e18),  # 1 CRO for cross-chain operations
        agent_name="Bridge Agent",
        description="Bridge assets between chains",
    ),
]

LIQUIDITY_AGENT_ROUTES = [
    RouteConfig(
        path="/liquidity",
        method="POST",
        network="cronos",
        asset="CRO",
        amount=int(0.3 * 1e18),  # 0.3 CRO for liquidity operations
        agent_name="Liquidity Agent",
        description="Manage liquidity pools",
    ),
]

LENDING_AGENT_ROUTES = [
    RouteConfig(
        path="/lending",
        method="POST",
        network="cronos",
        asset="CRO",
        amount=int(0.2 * 1e18),  # 0.2 CRO for lending operations
        agent_name="Lending Agent",
        description="Lending protocol operations",
    ),
]

YIELD_OPTIMIZER_AGENT_ROUTES = [
    RouteConfig(
        path="/yield_optimizer",
        method="POST",
        network="cronos",
        asset="CRO",
        amount=int(0.25 * 1e18),  # 0.25 CRO for yield optimization
        agent_name="Yield Optimizer Agent",
        description="Optimize yield strategies",
    ),
]

# Routes configuration dictionary for easy reference
AGENTS_ROUTE_CONFIG = {
    "balance": BALANCE_AGENT_ROUTES,
    "transfer": TRANSFER_AGENT_ROUTES,
    "swap": SWAP_AGENT_ROUTES,
    "bridge": BRIDGE_AGENT_ROUTES,
    "liquidity": LIQUIDITY_AGENT_ROUTES,
    "lending": LENDING_AGENT_ROUTES,
    "yield_optimizer": YIELD_OPTIMIZER_AGENT_ROUTES,
}
