"""
Balance Agent - Web3 Cryptocurrency Balance Checking Agent

This module implements an AI-powered agent that helps users check cryptocurrency
balances across multiple blockchain networks (Ethereum, BNB, Polygon, Cronos, etc.).

Cronos support:
- Uses Bitquery GraphQL API to fetch balances
- Supports Ethereum-compatible addresses (0x format)
- Network parameter: "cronos"
- Fetches all fungible asset balances including native CRO token
- Requires BITQUERY_API_KEY environment variable

ARCHITECTURE OVERVIEW:
----------------------
The agent follows a multi-layered architecture:

1. LangGraph Agent Layer:
   - Uses LangGraph v1.0+ create_agent() API to build the core AI agent
   - Powered by OpenAI's ChatOpenAI model (configurable via OPENAI_MODEL env var)
   - Has access to tools: get_balance() and get_token_balance()
   - Uses a system prompt that guides the agent on how to handle balance queries

2. A2A (Agent-to-Agent) Integration Layer:
   - Implements AgentExecutor interface for A2A protocol compatibility
   - Creates AgentCard for agent discovery and capabilities
   - Uses A2AStarletteApplication to expose the agent as an HTTP service
   - Handles request/response through DefaultRequestHandler

3. Google ADK (Agent Development Kit) Layer:
   - Uses Runner to orchestrate agent execution
   - InMemoryArtifactService for artifact storage
   - InMemorySessionService for session management
   - InMemoryMemoryService for conversation memory

4. Server Layer:
   - Exposes agent via Starlette/FastAPI application
   - Can run standalone (on configurable port) or be mounted as a sub-application
   - Provides agent card endpoint for discovery

WORKFLOW:
---------
1. User sends a query (e.g., "get balance of 0x742d35... on ethereum")
2. RequestContext captures the user input
3. BalanceAgentExecutor.execute() is called
4. BalanceAgent.invoke() processes the query:
   - Validates OpenAI API key
   - Invokes LangGraph agent with user query
   - Agent uses tools to fetch balance data (currently stubbed)
   - Extracts assistant response from agent result
5. Response is formatted as JSON and sent back via EventQueue

KEY COMPONENTS:
---------------
- BalanceAgent: Core agent class that wraps LangGraph agent and ADK Runner
- BalanceAgentExecutor: Implements A2A AgentExecutor interface
- Tools: get_balance() and get_token_balance() for blockchain queries
- create_server(): Factory function to create A2A server (standalone or mounted)

ENVIRONMENT VARIABLES:
----------------------
- OPENAI_API_KEY: Required - OpenAI API key for LLM access
- BITQUERY_API_KEY: Required - Bitquery API key for Cronos balance queries
- OPENAI_MODEL: Optional - Model name (default: "gpt-4o-mini")
- ITINERARY_PORT: Optional - Server port (default: 9001)
- RENDER_EXTERNAL_URL: Optional - External URL for agent card
- CRONOS_NETWORK: Optional - Network to use (default: "mainnet")

USAGE:
------
Standalone mode:
    python -m app.agents.balance.agent
    # Server starts on http://0.0.0.0:9001 (or ITINERARY_PORT)

Mounted mode:
    from app.agents.balance.agent import create_server
    app.mount("/balance", create_server(base_url="http://localhost:8000/balance"))

NOTES:
------
- Cronos balance fetching is fully implemented using Bitquery API
- Other networks (Ethereum, BNB, etc.) are stubbed and will be implemented later
- Uses in-memory services (sessions, artifacts, memory) - not persistent
- Error handling includes user-friendly messages for common issues
- Supports streaming responses via AgentCapabilities
- Bitquery API supports both v1 and v2 tokens (auto-detected)
"""

import os
import uuid
import json
import pathlib
from decimal import Decimal, ROUND_DOWN
from typing import Any, List, Dict, Optional
import time

# Simple in-memory cache to avoid excessive Bitquery calls
# Keyed by network:address (lowercased)
BALANCE_CACHE_TTL = int(os.getenv("BALANCE_CACHE_TTL", "600"))  # seconds
_BALANCE_CACHE: Dict[str, Dict[str, Any]] = {}  # { key: {"timestamp": float, "data": dict} }

import uvicorn
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
# Try to load from backend directory first, then current directory
backend_dir = pathlib.Path(__file__).parent.parent.parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback to current directory

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Message,
    Part,
    Role,
    TextPart,
)
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

# Constants
DEFAULT_PORT = 9001
DEFAULT_NETWORK = "ethereum"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0
DEFAULT_SESSION_ID = "default_session"
EMPTY_RESPONSE_MESSAGE = (
    "I apologize, but I couldn't generate a response. Please try rephrasing your question."
)

# Environment variables
ENV_ITINERARY_PORT = "ITINERARY_PORT"
ENV_RENDER_EXTERNAL_URL = "RENDER_EXTERNAL_URL"
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_OPENAI_MODEL = "OPENAI_MODEL"
ENV_BITQUERY_API_KEY = "BITQUERY_API_KEY"
ENV_CRONOS_NETWORK = "CRONOS_NETWORK"

# Bitquery API endpoints
BITQUERY_API_V1_URL = "https://graphql.bitquery.io"
BITQUERY_API_V2_URL = "https://graphql.bitquery.io/v2"

# GraphQL query to get user token balances using Bitquery API v2
# This query fetches native CRO balance and all token balances for an address on Cronos
GET_USER_BALANCES_QUERY = """
query GetCronosBalances($address: String!) {
  ethereum(network: cronos) {
    address(address: {is: $address}) {
      # Native coin balance (CRO)
      balance
      # Token balances (CRC-20)
      balances {
        currency {
          name
          symbol
          decimals
          address
        }
        value
      }
    }
  }
}
"""

# Message types
MESSAGE_TYPE_AI = "ai"
MESSAGE_ROLE_ASSISTANT = "assistant"
MESSAGE_ROLE_USER = "user"
MESSAGE_KEY_MESSAGES = "messages"
MESSAGE_KEY_OUTPUT = "output"
MESSAGE_KEY_CONTENT = "content"
MESSAGE_KEY_ROLE = "role"
MESSAGE_KEY_TYPE = "type"

# Error messages
ERROR_API_KEY = "api key"
ERROR_TIMEOUT = "timeout"
ERROR_AUTH_MESSAGE = "Authentication error: Please check your OpenAI API key configuration."
ERROR_TIMEOUT_MESSAGE = "Request timed out. Please try again."
ERROR_GENERIC_PREFIX = "I encountered an error while processing your request: "


def get_system_prompt() -> str:
    """Get the system prompt for the agent."""
    return """You are a helpful Web3 assistant specializing in checking cryptocurrency balances.

When users ask about balances:
1. Extract the wallet address:
   - If the user explicitly provides a wallet address (format: 0x...), use that address
   - If the user says "my balance", "fetch my balance", "check my balance", "get my balance", etc.:
     * Check the conversation context for a connected wallet address
     * If a connected wallet address is found in context, automatically use it
     * If no connected wallet is in context, politely ask the user for their wallet address
   - Always prioritize user-provided addresses over context addresses
2. Determine which network they're asking about:
   - For Cronos: use "cronos"
   - Default to "cronos" if not specified
3. For token queries, identify the token symbol (USDC, USDT, DAI, CRO, etc.)
4. Use the appropriate tool to fetch balance data
5. Present results in a clear, user-friendly format

Special handling for Cronos:
- Cronos uses Ethereum-compatible addresses (0x format)
- Default network is "cronos" for this application
- When user says "get my balance" or similar, automatically use connected wallet if available in context
- The network parameter should be "cronos"

Address validation:
- Addresses should start with 0x and contain valid hexadecimal characters
- If there's an error, explain it clearly and suggest alternatives."""


def get_port() -> int:
    """Get the port number from environment or default."""
    return int(os.getenv(ENV_ITINERARY_PORT, str(DEFAULT_PORT)))


def get_card_url(port: int) -> str:
    """Get the card URL from environment or construct from port."""
    return os.getenv(ENV_RENDER_EXTERNAL_URL, f"http://localhost:{port}")


def create_agent_skill() -> AgentSkill:
    """Create the agent skill definition."""
    return AgentSkill(
        id="balance_agent",
        name="Balance Agent",
        description="Balance Agent for checking crypto balances on Cronos",
        tags=["balance", "cronos", "web3", "crypto"],
        examples=[
            "get balance",
            "get my balance",
            "give my balance",
            "get balance on cronos",
            "get balance of 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "get balance of usdc on cronos",
            "check my USDT balance",
            "get my balance on cronos",
        ],
    )


def create_agent_card(port: int) -> AgentCard:
    """Create the public agent card."""
    card_url = get_card_url(port)
    skill = create_agent_skill()
    return AgentCard(
        name="Balance Agent",
        description=(
            "LangGraph powered agent that helps to get "
            "cryptocurrency balances across multiple chains"
        ),
        url=card_url,
        version="2.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
        supports_authenticated_extended_card=False,
    )


def validate_address(address: str) -> bool:
    """Validate Ethereum/Cronos address format.
    
    Args:
        address: Address to validate
        
    Returns:
        True if address is valid, False otherwise
    """
    if not address.startswith("0x"):
        return False
    if len(address) < 3:
        return False
    hex_part = address[2:]
    if not all(c in "0123456789abcdefABCDEF" for c in hex_part):
        return False
    return True


def get_bitquery_api_key() -> str:
    """Get Bitquery API key from environment or raise error.
    
    Returns:
        Bitquery API key
        
    Raises:
        ValueError: If no API key is found
    """
    api_key = os.getenv(ENV_BITQUERY_API_KEY)
    if not api_key:
        # Check if .env file exists and provide helpful error message
        backend_dir = pathlib.Path(__file__).parent.parent.parent.parent
        env_path = backend_dir / ".env"
        env_exists = env_path.exists()
        
        error_msg = (
            "BITQUERY_API_KEY environment variable is required but not found.\n"
            f"Please set it in your .env file or as an environment variable.\n"
        )
        if env_exists:
            error_msg += (
                f"Found .env file at: {env_path}\n"
                f"Please add BITQUERY_API_KEY=your-api-key-here to this file.\n"
            )
        else:
            error_msg += (
                f"Could not find .env file at: {env_path}\n"
                f"Please create a .env file in the backend directory with BITQUERY_API_KEY=your-api-key-here\n"
            )
        error_msg += "Get your free API key at: https://bitquery.io/"
        raise ValueError(error_msg)
    
    # Check if API key is empty or just whitespace
    if not api_key.strip():
        raise ValueError(
            "BITQUERY_API_KEY is set but appears to be empty.\n"
            "Please check your .env file and ensure the API key value is not empty."
        )
    
    return api_key.strip()


def format_balance(amount: str, decimals: int = 18) -> str:
    """Format balance from string amount to human-readable format.
    
    Args:
        amount: Balance as string (from GraphQL response)
        decimals: Number of decimals (default: 18)
        
    Returns:
        Formatted balance string
    """
    try:
        # Handle both string and numeric inputs
        if isinstance(amount, str):
            # Check if it's already a decimal number (has a dot)
            if '.' in amount:
                # Already in human-readable format
                return f"{float(amount):.6f}"
            # Otherwise, it's in smallest units (wei/satoshi)
            amount_int = int(amount)
        else:
            amount_int = int(amount)
        
        # Convert from smallest unit to human-readable
        if decimals > 0:
            balance = amount_int / (10 ** decimals)
        else:
            balance = float(amount_int)
        
        # Return formatted with up to 6 decimal places, removing trailing zeros
        formatted = f"{balance:.6f}".rstrip('0').rstrip('.')
        return formatted if formatted else "0"
    except (ValueError, TypeError) as e:
        # If conversion fails, return the original value
        return str(amount)


def _cache_key(address: str, network: str = "cronos") -> str:
    return f"{network}:{address.lower()}"


def fetch_cronos_balances(address: str) -> Dict[str, Any]:
    """Fetch balances from Cronos using Bitquery API.

    Fetches all tokens with balance > 0 from Bitquery.
    Zero balance tokens are excluded.

    Uses a simple in-memory cache to avoid repeated calls to Bitquery. Cached entries
    are stored for BALANCE_CACHE_TTL seconds and returned directly when valid.

    Args:
        address: Wallet address to check

    Returns:
        Dictionary with balance information
    """
    try:
        # Validate address format
        if not validate_address(address):
            return {
                "success": False,
                "error": f"Invalid address format: {address}. Address must start with 0x and contain valid hexadecimal characters.",
            }

        # Check cache first
        key = _cache_key(address, "cronos")
        cache_entry = _BALANCE_CACHE.get(key)
        if cache_entry:
            age = time.time() - float(cache_entry.get("timestamp", 0))
            if age < BALANCE_CACHE_TTL:
                print(f"Debug: cache hit for {address} (age={age:.1f}s)")
                cached = cache_entry["data"].copy()
                cached["cached"] = True
                return cached
            else:
                print(f"Debug: cache expired for {address} (age={age:.1f}s)")
                _BALANCE_CACHE.pop(key, None)

        # Get API key - catch ValueError if missing
        try:
            api_key = get_bitquery_api_key()
        except ValueError as e:
            return {
                "address": address,
                "success": False,
                "error": str(e),
            }

        variables = {
            "address": address,
        }
        payload = {
            "query": GET_USER_BALANCES_QUERY,
            "variables": variables,
        }
        
        # Determine API version and set headers/URL accordingly
        # API v2 tokens typically start with "ory_at_" and use Authorization header
        # API v1 tokens use X-API-KEY header
        is_v2_token = api_key.startswith("ory_at_") or api_key.startswith("Bearer ")
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if is_v2_token:
            # API v2 uses Authorization header with Bearer token
            if not api_key.startswith("Bearer "):
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers["Authorization"] = api_key
            api_url = BITQUERY_API_V2_URL
        else:
            # API v1 uses X-API-KEY header
            headers["X-API-KEY"] = api_key
            api_url = BITQUERY_API_V1_URL
        
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=30,
        )
        
        if response.status_code == 401:
            error_detail = "Unauthorized - Invalid API key. Please check your BITQUERY_API_KEY."
            try:
                error_data = response.json()
                if "errors" in error_data:
                    error_detail += f" Details: {json.dumps(error_data['errors'])}"
                elif "message" in error_data:
                    error_detail += f" Details: {error_data['message']}"
            except:
                error_detail += f" Response: {response.text[:200]}"
            return {
                "address": address,
                "error": error_detail,
                "success": False,
            }
        if response.status_code == 403:
            error_detail = "Forbidden - The API endpoint may require authentication or have access restrictions."
            try:
                error_data = response.json()
                if "errors" in error_data:
                    error_detail += f" Details: {json.dumps(error_data['errors'])}"
            except:
                error_detail += f" Response: {response.text[:200]}"
            return {
                "address": address,
                "error": error_detail,
                "success": False,
            }
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            return {
                "address": address,
                "error": f"GraphQL errors: {json.dumps(data['errors'])}",
                "success": False,
            }
        
        # Parse Bitquery API v2 response structure
        ethereum_data = data.get("data", {}).get("ethereum", {})
        address_data = ethereum_data.get("address", [])
        
        if not address_data:
            # Address not found or has never had any activity - return zero balance
            return {
                "address": address,
                "balances": [{
                    "currency": {"name": "Cronos", "symbol": "CRO"},
                    "value": "0",
                    "symbol": "CRO",
                    "name": "Cronos",
                    "decimals": 18,
                    "contract": "",
                    "is_native": True,
                }],
                "success": True,
                "total_fetched": 1,
                "filtered_out": 0,
            }
        
        address_info = address_data[0]
        # Handle case where balance might be None, missing, or empty string
        native_balance = address_info.get("balance")
        if native_balance is None or native_balance == "":
            native_balance = "0"
        balances_list = address_info.get("balances", []) or []
        
        # Transform Bitquery format to our standard format
        formatted_balances = []
        
        # Always add native CRO balance (even if 0) so users can see their balance status
        try:
            # Bitquery returns native balance in different formats:
            # - As decimal string (e.g., "24827.849010682339425216") - already in CRO units
            # - As integer string in wei (e.g., "24827849010682339425216") - in smallest units
            # - May be "0", "0.0", or None if balance is zero
            # We need to detect the format and convert to wei (smallest units) for storage
            native_balance_str = str(native_balance).strip() if native_balance else "0"
            
            if '.' in native_balance_str:
                # Already in decimal format (CRO units), convert to wei
                # Use Decimal for precision with large numbers
                native_balance_decimal = Decimal(native_balance_str)
                # Convert from CRO to wei (multiply by 10^18), even if 0
                wei_multiplier = Decimal(10) ** 18
                native_balance_wei = int(native_balance_decimal * wei_multiplier)
                formatted_balances.append({
                    "currency": {"name": "Cronos", "symbol": "CRO"},
                    "value": str(native_balance_wei),
                    "symbol": "CRO",
                    "name": "Cronos",
                    "decimals": 18,
                    "contract": "",
                    "is_native": True,
                })
            else:
                # Already in wei (smallest units), use as-is (even if 0)
                native_balance_int = int(native_balance_str) if native_balance_str else 0
                formatted_balances.append({
                    "currency": {"name": "Cronos", "symbol": "CRO"},
                    "value": str(native_balance_int),
                    "symbol": "CRO",
                    "name": "Cronos",
                    "decimals": 18,
                    "contract": "",
                    "is_native": True,
                })
        except (ValueError, TypeError) as e:
            # If parsing fails, default to 0 balance
            print(f"Error parsing native balance '{native_balance}': {e}, defaulting to 0")
            formatted_balances.append({
                "currency": {"name": "Cronos", "symbol": "CRO"},
                "value": "0",
                "symbol": "CRO",
                "name": "Cronos",
                "decimals": 18,
                "contract": "",
                "is_native": True,
            })
        
        # Add token balances
        for balance in balances_list:
            currency = balance.get("currency", {})
            value = balance.get("value", "0")
            
            # Skip zero balances
            try:
                value_float = float(value)
                if value_float == 0:
                    continue
            except (ValueError, TypeError):
                continue
            
            # Get decimals - handle None or missing values
            decimals_raw = currency.get("decimals")
            decimals = None
            if decimals_raw is not None:
                try:
                    decimals = int(decimals_raw)
                except (ValueError, TypeError):
                    decimals = None

            # If decimals missing, attempt to fetch from chain via RPC using eth_call to decimals()
            if decimals is None:
                contract_addr = currency.get("address", "") or ""
                rpc_url = os.getenv("CRONOS_RPC_URL", "https://evm-cronos.crypto.org")
                if contract_addr:
                    try:
                        hex_address = contract_addr if contract_addr.startswith("0x") else f"0x{contract_addr}"
                        payload_rpc = {
                            "jsonrpc": "2.0",
                            "method": "eth_call",
                            "params": [
                                {"to": hex_address, "data": "0x313ce567"},
                                "latest",
                            ],
                            "id": 1,
                        }
                        rpc_resp = requests.post(rpc_url, json=payload_rpc, timeout=10)
                        rpc_resp.raise_for_status()
                        rpc_data = rpc_resp.json()
                        rpc_result = rpc_data.get("result")
                        if rpc_result and rpc_result != "0x":
                            decimals = int(rpc_result, 16)
                            print(f"Debug: fetched decimals={decimals} for {hex_address} via RPC")
                    except Exception as e:
                        print(f"Debug: unable to fetch decimals for {contract_addr} via RPC: {e}")

            # Default to 18 if still unknown
            if decimals is None:
                decimals = 18

            # Bitquery v2 might return value in different formats
            # It may return token amounts as decimals (e.g., 0.200826 USDT) or as integers in smallest units
            # Use Decimal to precisely detect and convert fractional token amounts to smallest units
            try:
                value_in_smallest = "0"
                try:
                    value_dec = Decimal(str(value))
                except Exception:
                    value_dec = None

                if value_dec is not None:
                    # If the value has fractional part, treat it as token units and multiply by 10^decimals
                    if value_dec != value_dec.to_integral_value():
                        value_in_smallest = str(int((value_dec * (Decimal(10) ** decimals)).to_integral_value(rounding=ROUND_DOWN)))
                    else:
                        # Integer value - assume it's already in smallest units
                        value_in_smallest = str(int(value_dec))
                else:
                    # Fallback: use the parsed float (previous behavior)
                    value_in_smallest = str(int(Decimal(str(int(value_float)))))
            except Exception as e:
                print(f"Debug: failed to convert token value for {currency.get('symbol')} value={value} decimals={decimals}: {e}")
                try:
                    value_in_smallest = str(int(Decimal(str(value))))
                except Exception:
                    value_in_smallest = "0"

            print(f"Debug: token {currency.get('symbol')} value={value} decimals_raw={decimals_raw} resolved_decimals={decimals} value_in_smallest={value_in_smallest}")

            formatted_balance = {
                "currency": currency,
                "value": value_in_smallest,  # Always store in smallest units for consistency
                "symbol": currency.get("symbol", "Unknown"),
                "name": currency.get("name", "Unknown"),
                "decimals": decimals,
                "contract": currency.get("address", ""),
                "is_native": False,
            }
            formatted_balances.append(formatted_balance)
        
        # Filter out test tokens
        def is_test_token(balance: Dict) -> bool:
            """Check if a token is a test token."""
            name = (balance.get("name") or "").lower()
            symbol = (balance.get("symbol") or "").lower()
            # Only filter tokens that clearly indicate test tokens in name or symbol
            return "test" in name or "test" in symbol
        
        filtered_balances = [b for b in formatted_balances if not is_test_token(b)]
        
        # Debug: log counts to help troubleshoot missing tokens
        filtered_out_count = len(formatted_balances) - len(filtered_balances)
        print(f"Debug: address={address} raw_balances={len(balances_list)} formatted={len(formatted_balances)} filtered_out={filtered_out_count}")
        if filtered_out_count > 0:
            print("Debug: filtered out sample:", formatted_balances[:min(5, len(formatted_balances))])
        
        # Sort balances: native CRO first, then by value descending
        def sort_key(balance: Dict) -> tuple:
            """Sort key: native token first, then by value descending."""
            is_native = balance.get("is_native", False)
            try:
                value = float(balance.get("value", "0"))
            except (ValueError, TypeError):
                value = 0
            return (not is_native, -value)
        
        filtered_balances.sort(key=sort_key)

        result = {
            "address": address,
            "balances": filtered_balances,
            "success": True,
            "total_fetched": len(filtered_balances),
            "filtered_out": filtered_out_count,
            "raw_balances_count": len(balances_list),
            "formatted_sample": formatted_balances[:3],
            "cached": False,
        }

        # Store in cache
        try:
            _BALANCE_CACHE[key] = {"timestamp": time.time(), "data": result}
            print(f"Debug: cached balance for {address}")
        except Exception as e:
            print(f"Debug: failed to cache balance for {address}: {e}")

        return result
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error: {str(e)}"
        print(f"Balance fetch request error for {address}: {error_msg}")
        return {
            "address": address,
            "error": error_msg,
            "success": False,
        }
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Balance fetch unexpected error for {address}: {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            "address": address,
            "error": error_msg,
            "success": False,
        }


def format_cronos_balance_response(balances_data: Dict[str, Any], address: str) -> str:
    """Format Cronos balance data into a user-friendly string.
    
    Args:
        balances_data: Dictionary with balance data from Bitquery
        address: Wallet address
        
    Returns:
        Formatted balance string
    """
    if not balances_data.get("success", False):
        return f"Error fetching Cronos balance: {balances_data.get('error', 'Unknown error')}"
    balances = balances_data.get("balances", [])
    
    # Always show at least native CRO balance (even if 0)
    # Check if we have any balances, or if all balances are zero
    has_non_zero_balance = False
    native_balance_shown = False
    
    for balance in balances:
        if balance.get("is_native", False):
            native_balance_shown = True
        value = balance.get("value", "0")
        try:
            if int(value) > 0:
                has_non_zero_balance = True
                break
        except (ValueError, TypeError):
            pass
    
    # If no balances returned or no native balance shown, create a default zero balance response
    if not balances or not native_balance_shown:
        result_lines = [f"Cronos balances for {address}:\n"]
        result_lines.append("1. Cronos (CRO)")
        result_lines.append("   Type: Native CRO")
        result_lines.append("   Balance: 0.000000 CRO")
        result_lines.append("\n✅ Balance check successful. This address has 0 CRO and no token balances.")
        return "\n".join(result_lines)
    
    # If we have balances but all are zero, show them anyway with a clear message
    if not has_non_zero_balance:
        result_lines = [f"Cronos balances for {address}:\n"]
        result_lines.append("✅ Balance check successful. All balances are currently 0:")
        result_lines.append("")
    else:
        result_lines = [f"Cronos balances for {address}:\n"]
    for idx, balance in enumerate(balances, 1):
        value = balance.get("value", "0")
        symbol = balance.get("symbol", "Unknown")
        name = balance.get("name", "Unknown")
        decimals = int(balance.get("decimals", 18))
        contract = balance.get("contract", "")
        is_native = balance.get("is_native", False)
        
        # Format balance with proper precision
        try:
            value_int = int(value)
            if decimals > 0:
                balance_decimal = value_int / (10 ** decimals)
                # Use more precision for very small values
                if balance_decimal < 0.000001:
                    formatted_balance = f"{balance_decimal:.18f}".rstrip('0').rstrip('.')
                else:
                    formatted_balance = f"{balance_decimal:.6f}".rstrip('0').rstrip('.')
            else:
                formatted_balance = str(value_int)
        except (ValueError, TypeError):
            formatted_balance = str(value)
        
        result_lines.append(f"{idx}. {name} ({symbol})")
        if contract and not is_native:
            result_lines.append(f"   Contract: {contract}")
        elif is_native:
            result_lines.append(f"   Type: Native CRO")
        result_lines.append(f"   Balance: {formatted_balance} {symbol}")
    
    filtered_out = balances_data.get("filtered_out", 0)
    if filtered_out > 0:
        result_lines.append(f"\nNote: {filtered_out} test token(s) filtered out")
    
    return "\n".join(result_lines)


@tool
def get_balance(address: str, network: str = DEFAULT_NETWORK) -> str:
    """Get the balance of a cryptocurrency address on Cronos.

    Args:
        address: The cryptocurrency wallet address (0x... format)
        network: The blockchain network (cronos)

    Returns:
        The balance as a string
    """
    network_lower = network.lower()
    if network_lower in ["cronos"]:
        balances_data = fetch_cronos_balances(address)
        return format_cronos_balance_response(balances_data, address)
    return f"Balance for {address} on {network}: Not implemented yet (only Cronos is currently supported)"


@tool
def get_token_balance(address: str, token: str, network: str = DEFAULT_NETWORK) -> str:
    """Get the balance of a specific token for an address on Cronos.

    Args:
        address: The cryptocurrency wallet address (0x... format)
        token: The token symbol (e.g., USDC, USDT, DAI, CRO)
        network: The blockchain network (cronos)

    Returns:
        The token balance as a string
    """
    network_lower = network.lower()
    if network_lower in ["cronos"]:
        balances_data = fetch_cronos_balances(address)
        if not balances_data.get("success", False):
            return f"Error fetching Cronos balance: {balances_data.get('error', 'Unknown error')}"
        balances = balances_data.get("balances", [])
        token_upper = token.upper()
        for balance in balances:
            symbol = balance.get("symbol", "").upper()
            if symbol == token_upper or token_upper in symbol:
                value = balance.get("value", "0")
                decimals = int(balance.get("decimals", 18))
                name = balance.get("name", "Unknown Token")
                try:
                    value_int = int(value)
                    formatted_balance = value_int / (10 ** decimals)
                    return f"{address} has {formatted_balance:.6f} {symbol} ({name}) on Cronos"
                except (ValueError, TypeError):
                    return f"{address} has {value} {symbol} (raw) on Cronos"
        return f"No {token_upper} balance found for {address} on Cronos"
    return f"Token balance for {address}: {token.upper()} on {network} - Not implemented yet (only Cronos is currently supported)"


def get_tools() -> List[Any]:
    """Get the list of tools available to the agent."""
    return [get_balance, get_token_balance]


def validate_openai_api_key() -> None:
    """Validate that OpenAI API key is set."""
    openai_api_key = os.getenv(ENV_OPENAI_API_KEY)
    if not openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required.\n"
            "Please set it before running the agent:\n"
            "  export OPENAI_API_KEY=your-api-key-here\n"
            "Or add it to your environment configuration."
        )


def create_chat_model() -> ChatOpenAI:
    """Create and configure the ChatOpenAI model."""
    model_name = os.getenv(ENV_OPENAI_MODEL, DEFAULT_MODEL)
    return ChatOpenAI(model=model_name, temperature=DEFAULT_TEMPERATURE)


def is_assistant_message(message: Any) -> bool:
    """Check if a message is from the assistant."""
    if hasattr(message, MESSAGE_KEY_TYPE) and hasattr(message, MESSAGE_KEY_CONTENT):
        return (
            message.type == MESSAGE_TYPE_AI
            or getattr(message, MESSAGE_KEY_ROLE, None) == MESSAGE_ROLE_ASSISTANT
        )
    if isinstance(message, dict):
        return (
            message.get(MESSAGE_KEY_ROLE) == MESSAGE_ROLE_ASSISTANT
            or message.get(MESSAGE_KEY_TYPE) == MESSAGE_TYPE_AI
        )
    return False


def extract_message_content(message: Any) -> str:
    """Extract content from a message object."""
    if hasattr(message, MESSAGE_KEY_CONTENT):
        return message.content
    if isinstance(message, dict):
        return message.get(MESSAGE_KEY_CONTENT, "")
    return ""


def extract_assistant_response(result: Any) -> str:
    """Extract the assistant's response from the agent result."""
    if not isinstance(result, dict) or MESSAGE_KEY_MESSAGES not in result:
        return _extract_fallback_output(result)
    messages = result[MESSAGE_KEY_MESSAGES]
    if not messages:
        return _extract_fallback_output(result)
    assistant_content = _find_assistant_message(messages)
    if assistant_content:
        return assistant_content
    return _extract_last_message_content(messages)


def _find_assistant_message(messages: List[Any]) -> str:
    """Find the last assistant message in the messages list."""
    for message in reversed(messages):
        if is_assistant_message(message):
            content = extract_message_content(message)
            if content:
                return content
    return ""


def _extract_last_message_content(messages: List[Any]) -> str:
    """Extract content from the last message as fallback."""
    if not messages:
        return ""
    last_message = messages[-1]
    return extract_message_content(last_message)


def _extract_fallback_output(result: Any) -> str:
    """Extract output from result dictionary or convert to string."""
    if isinstance(result, dict):
        return result.get(MESSAGE_KEY_OUTPUT, "")
    return str(result)


def format_error_message(error: Exception) -> str:
    """Format error message for user-friendly display."""
    error_msg = str(error).lower()
    if ERROR_API_KEY in error_msg:
        return ERROR_AUTH_MESSAGE
    if ERROR_TIMEOUT in error_msg:
        return ERROR_TIMEOUT_MESSAGE
    return f"{ERROR_GENERIC_PREFIX}{error}. Please try again."


class BalanceAgent:
    def __init__(self):
        self._agent = self._build_agent()
        self._runner = Runner(
            app_name="balanceagent",
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def _build_agent(self):
        """Build the agent using the new create_agent API."""
        validate_openai_api_key()
        model = create_chat_model()
        tools = get_tools()
        system_prompt = get_system_prompt()
        return create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
        )

    async def invoke(self, query: str, session_id: str) -> str:
        """Invoke the agent with a query."""
        try:
            result = await self._invoke_agent(query, session_id)
            output = extract_assistant_response(result)
            validated_output = self._validate_output(output)
            # Return as JSON string to ensure compatibility with ADK agent expectations
            return json.dumps({"response": validated_output, "success": True})
        except Exception as e:
            print(f"Error in agent invoke: {e}")
            error_message = format_error_message(e)
            # Return error as JSON string
            return json.dumps({"response": error_message, "success": False, "error": str(e)})

    async def _invoke_agent(self, query: str, session_id: str) -> Any:
        """Invoke the agent with the given query and session."""
        return await self._agent.ainvoke(
            {"messages": [{MESSAGE_KEY_ROLE: MESSAGE_ROLE_USER, MESSAGE_KEY_CONTENT: query}]},
            config={"configurable": {"thread_id": session_id}},
        )

    def _validate_output(self, output: str) -> str:
        """Validate and return output, or return default message if empty."""
        if not output or not output.strip():
            return EMPTY_RESPONSE_MESSAGE
        return output


def get_session_id(context: RequestContext) -> str:
    """Extract session ID from context or return default."""
    return getattr(context, "context_id", DEFAULT_SESSION_ID)


def create_message(content: str) -> Message:
    """Create a message object with the given content."""
    return Message(
        message_id=str(uuid.uuid4()),
        role=Role.agent,
        parts=[Part(root=TextPart(kind="text", text=content))],
    )


class BalanceAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = BalanceAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute the agent's logic for a given request context."""
        query = context.get_user_input()
        session_id = get_session_id(context)
        final_content = await self.agent.invoke(query, session_id)
        message = create_message(final_content)
        await event_queue.enqueue_event(message)

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Request the agent to cancel an ongoing task."""
        raise NotImplementedError("cancel not supported")


def create_balance_agent_app(card_url: str) -> A2AStarletteApplication:
    """Create and configure the A2A server application for the balance agent.

    Args:
        card_url: The base URL where the agent card will be accessible

    Returns:
        A2AStarletteApplication instance configured for the balance agent
    """
    agent_card = AgentCard(
        name="Balance Agent",
        description=(
            "LangGraph powered agent that helps to get "
            "cryptocurrency balances across multiple chains"
        ),
        url=card_url,
        version="2.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[create_agent_skill()],
        supports_authenticated_extended_card=False,
    )
    request_handler = DefaultRequestHandler(
        agent_executor=BalanceAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
        extended_agent_card=agent_card,
    )
