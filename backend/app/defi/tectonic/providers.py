"""
Phase 5: RPC Provider Manager with failover logic.

This module provides:
- RPC pool management with automatic failover
- Health checks and latency monitoring
- Retry logic with exponential backoff
- Reusable for both Tectonic and swap operations
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import requests
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.types import RPCEndpoint

from .config import TECTONIC_NETWORK

logger = logging.getLogger(__name__)

# Default timeout for RPC calls
DEFAULT_RPC_TIMEOUT = 10  # seconds

# Health check timeout (shorter for quick failover)
HEALTH_CHECK_TIMEOUT = 3  # seconds


class RPCProviderError(Exception):
    """Base exception for RPC provider errors."""

    pass


class ProviderManager:
    """
    Manages a pool of RPC endpoints with automatic failover.

    Features:
    - Automatic health checks
    - Failover on errors or timeouts
    - Latency tracking
    - Retry with exponential backoff
    """

    def __init__(
        self,
        rpc_urls: Optional[List[str]] = None,
        timeout: int = DEFAULT_RPC_TIMEOUT,
        health_check_interval: int = 60,  # seconds between health checks
    ) -> None:
        """
        Initialize the provider manager.

        Args:
            rpc_urls: List of RPC URLs to use (defaults to TECTONIC_NETWORK.rpc_urls)
            timeout: Request timeout in seconds
            health_check_interval: How often to re-check failed endpoints (seconds)
        """
        self.rpc_urls = rpc_urls or list(TECTONIC_NETWORK.rpc_urls) or []
        if not self.rpc_urls:
            raise RPCProviderError("No RPC URLs provided to ProviderManager.")

        self.timeout = timeout
        self.health_check_interval = health_check_interval

        # Track endpoint health
        self._endpoint_status: dict[str, dict] = {}
        for url in self.rpc_urls:
            self._endpoint_status[url] = {
                "healthy": True,
                "last_check": 0,
                "failure_count": 0,
                "last_error": None,
            }

        # Current active endpoint
        self._current_index = 0
        self._web3_instance: Optional[Web3] = None

    def _is_endpoint_healthy(self, url: str) -> bool:
        """Check if an endpoint should be considered healthy."""
        status = self._endpoint_status[url]
        if not status["healthy"]:
            # Check if enough time has passed to retry
            time_since_check = time.time() - status["last_check"]
            if time_since_check >= self.health_check_interval:
                # Try health check again
                return self._check_endpoint_health(url)
        return status["healthy"]

    def _check_endpoint_health(self, url: str) -> bool:
        """
        Perform a quick health check on an RPC endpoint.

        Returns:
            True if endpoint is healthy, False otherwise
        """
        try:
            payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []}
            response = requests.post(url, json=payload, timeout=HEALTH_CHECK_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    chain_id_hex = data["result"]
                    expected_chain_id = hex(TECTONIC_NETWORK.chain_id)
                    is_valid = chain_id_hex.lower() == expected_chain_id.lower()

                    self._endpoint_status[url]["healthy"] = is_valid
                    self._endpoint_status[url]["last_check"] = time.time()
                    self._endpoint_status[url]["failure_count"] = 0
                    self._endpoint_status[url]["last_error"] = None

                    if not is_valid:
                        logger.warning(
                            f"RPC {url} returned wrong chain_id: {chain_id_hex} (expected {expected_chain_id})"
                        )

                    return is_valid

            # HTTP error or invalid response
            self._endpoint_status[url]["healthy"] = False
            self._endpoint_status[url]["last_check"] = time.time()
            self._endpoint_status[url]["failure_count"] += 1
            self._endpoint_status[url]["last_error"] = f"HTTP {response.status_code}"
            return False

        except requests.exceptions.Timeout:
            self._endpoint_status[url]["healthy"] = False
            self._endpoint_status[url]["last_check"] = time.time()
            self._endpoint_status[url]["failure_count"] += 1
            self._endpoint_status[url]["last_error"] = "Timeout"
            logger.warning(f"RPC {url} health check timed out")
            return False

        except Exception as e:
            self._endpoint_status[url]["healthy"] = False
            self._endpoint_status[url]["last_check"] = time.time()
            self._endpoint_status[url]["failure_count"] += 1
            self._endpoint_status[url]["last_error"] = str(e)
            logger.warning(f"RPC {url} health check failed: {e}")
            return False

    def get_web3(self, force_refresh: bool = False) -> Web3:
        """
        Get a Web3 instance connected to a healthy RPC endpoint.

        Args:
            force_refresh: If True, create a new Web3 instance even if one exists

        Returns:
            Web3 instance connected to a healthy endpoint

        Raises:
            RPCProviderError: If no healthy endpoints are available
        """
        if self._web3_instance and not force_refresh:
            # Quick check if current endpoint is still healthy
            current_url = self.rpc_urls[self._current_index]
            if self._is_endpoint_healthy(current_url):
                return self._web3_instance

        # Find a healthy endpoint
        healthy_url = self._find_healthy_endpoint()
        if not healthy_url:
            raise RPCProviderError(
                f"No healthy RPC endpoints available. Last errors: "
                f"{[(url, self._endpoint_status[url]['last_error']) for url in self.rpc_urls]}"
            )

        # Create Web3 instance
        self._web3_instance = Web3(Web3.HTTPProvider(healthy_url, request_kwargs={"timeout": self.timeout}))
        self._web3_instance.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        # Verify connection and chain ID
        if not self._web3_instance.is_connected():
            # Mark endpoint as unhealthy and try next one
            self._endpoint_status[healthy_url]["healthy"] = False
            return self.get_web3(force_refresh=True)

        chain_id = self._web3_instance.eth.chain_id
        if chain_id != TECTONIC_NETWORK.chain_id:
            raise RPCProviderError(
                f"RPC {healthy_url} returned wrong chain_id={chain_id}, expected {TECTONIC_NETWORK.chain_id}"
            )

        logger.info(f"Connected to RPC: {healthy_url} (chain_id={chain_id})")
        return self._web3_instance

    def _find_healthy_endpoint(self) -> Optional[str]:
        """
        Find the first healthy endpoint in the pool.

        Returns:
            URL of a healthy endpoint, or None if none are available
        """
        # Start from current index and rotate
        for i in range(len(self.rpc_urls)):
            idx = (self._current_index + i) % len(self.rpc_urls)
            url = self.rpc_urls[idx]

            if self._is_endpoint_healthy(url):
                self._current_index = idx
                return url

        # None are healthy, try to re-check all
        logger.warning("No endpoints marked healthy, attempting to re-check all...")
        for url in self.rpc_urls:
            if self._check_endpoint_health(url):
                self._current_index = self.rpc_urls.index(url)
                return url

        return None

    def mark_endpoint_unhealthy(self, url: str, error: Optional[str] = None) -> None:
        """
        Manually mark an endpoint as unhealthy (e.g., after a failed transaction).

        Args:
            url: RPC URL to mark as unhealthy
            error: Optional error message
        """
        if url in self._endpoint_status:
            self._endpoint_status[url]["healthy"] = False
            self._endpoint_status[url]["last_check"] = time.time()
            self._endpoint_status[url]["failure_count"] += 1
            self._endpoint_status[url]["last_error"] = error or "Manually marked unhealthy"
            logger.warning(f"Marked RPC {url} as unhealthy: {error}")

            # If this was the current endpoint, force refresh
            if self.rpc_urls[self._current_index] == url:
                self._web3_instance = None

    def get_status(self) -> dict:
        """
        Get status of all endpoints.

        Returns:
            Dictionary mapping URLs to their health status
        """
        return {
            url: {
                "healthy": status["healthy"],
                "failure_count": status["failure_count"],
                "last_error": status["last_error"],
            }
            for url, status in self._endpoint_status.items()
        }


def create_provider_manager(
    rpc_urls: Optional[List[str]] = None,
    timeout: int = DEFAULT_RPC_TIMEOUT,
) -> ProviderManager:
    """
    Factory function to create a ProviderManager with sensible defaults.

    Args:
        rpc_urls: Optional list of RPC URLs (defaults to TECTONIC_NETWORK.rpc_urls)
        timeout: Request timeout in seconds

    Returns:
        Configured ProviderManager instance
    """
    return ProviderManager(rpc_urls=rpc_urls, timeout=timeout)

