"""
OrderBook Agent - ClobX Trading Agent

This module implements an AI-powered agent that helps users trade on ClobX,
the fully on-chain Central Limit Order Book (CLOB) system on Cronos.

ARCHITECTURE OVERVIEW:
----------------------
Follows the same multi-layered architecture as other agents with LangGraph + A2A protocol.

WORKFLOW:
---------
1. User sends trading query (e.g., "place limit buy order for 100 MOVE at $1.50")
2. Agent processes query and executes appropriate trading operations
3. Supports: place orders, cancel orders, check order status, view order book

KEY COMPONENTS:
---------------
- OrderBookAgent: Core agent class with LangGraph integration
- OrderBookAgentExecutor: Implements A2A AgentExecutor interface
- Tools: place_limit_order(), place_market_order(), cancel_order(), get_order_book(), get_order_status()
- create_orderbook_agent_app(): Factory function

ENVIRONMENT VARIABLES:
----------------------
- OPENAI_API_KEY: Required - OpenAI API key
- OPENAI_MODEL: Optional - Model name (default: "gpt-4o-mini")
- CLOBX_API_URL: Required - ClobX API endpoint
- MOVEMENT_RPC_URL: Required - Cronos RPC
"""

import os
import uuid
import json
from typing import Any, List

from dotenv import load_dotenv
load_dotenv()

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
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0
DEFAULT_SESSION_ID = "default_session"
EMPTY_RESPONSE_MESSAGE = "I apologize, but I couldn't generate a response. Please try rephrasing your question."

# Environment variables
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_OPENAI_MODEL = "OPENAI_MODEL"

# Message constants
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
    return """You are a helpful trading assistant specializing in ClobX, the on-chain order book on Cronos.

When users want to trade:
1. Extract the trading pair (e.g., MOVE/USDC, ETH/USDC)
2. Determine order type: limit or market
3. Determine side: buy or sell
4. Extract price (for limit orders) and quantity
5. Use the appropriate tool to execute the trade

Available operations:
- Place limit orders (buy/sell at specific price)
- Place market orders (buy/sell at current market price)
- Cancel existing orders
- Check order status
- View order book depth

Always confirm order details before execution.
Explain slippage risks for market orders.
Provide order book context when relevant.
If there's an error, explain it clearly and suggest alternatives."""


def create_agent_skill() -> AgentSkill:
    """Create the agent skill definition."""
    return AgentSkill(
        id="orderbook_agent",
        name="OrderBook Agent",
        description="Trading agent for ClobX on-chain order book",
        tags=["trading", "orderbook", "clobx", "dex", "limit-orders"],
        examples=[
            "place limit buy order for 100 MOVE at $1.50",
            "sell 50 MOVE at market price",
            "cancel order #12345",
            "show MOVE/USDC order book",
            "check status of my orders",
        ],
    )


@tool
def place_limit_order(pair: str, side: str, price: str, quantity: str) -> str:
    """Place a limit order on ClobX.

    Args:
        pair: Trading pair (e.g., "MOVE/USDC")
        side: Order side ("buy" or "sell")
        price: Limit price
        quantity: Order quantity

    Returns:
        Order confirmation as JSON string
    """
    # TODO: Implement actual ClobX limit order placement
    return json.dumps({
        "status": "success",
        "order_id": "ORD-12345",
        "pair": pair,
        "side": side,
        "type": "limit",
        "price": price,
        "quantity": quantity,
        "filled": "0",
        "message": f"Limit {side} order placed successfully for {quantity} {pair} at ${price}"
    })


@tool
def place_market_order(pair: str, side: str, quantity: str) -> str:
    """Place a market order on ClobX.

    Args:
        pair: Trading pair (e.g., "MOVE/USDC")
        side: Order side ("buy" or "sell")
        quantity: Order quantity

    Returns:
        Order confirmation as JSON string
    """
    # TODO: Implement actual ClobX market order placement
    return json.dumps({
        "status": "success",
        "order_id": "ORD-12346",
        "pair": pair,
        "side": side,
        "type": "market",
        "quantity": quantity,
        "filled": quantity,
        "avg_price": "1.52",
        "message": f"Market {side} order executed for {quantity} {pair}"
    })


@tool
def cancel_order(order_id: str) -> str:
    """Cancel an existing order on ClobX.

    Args:
        order_id: The order ID to cancel

    Returns:
        Cancellation confirmation as JSON string
    """
    # TODO: Implement actual order cancellation
    return json.dumps({
        "status": "success",
        "order_id": order_id,
        "message": f"Order {order_id} cancelled successfully"
    })


@tool
def get_order_book(pair: str, depth: int = 10) -> str:
    """Get the order book for a trading pair.

    Args:
        pair: Trading pair (e.g., "MOVE/USDC")
        depth: Number of price levels to show (default: 10)

    Returns:
        Order book data as JSON string
    """
    # TODO: Implement actual order book fetching
    return json.dumps({
        "pair": pair,
        "bids": [
            {"price": "1.50", "quantity": "1000"},
            {"price": "1.49", "quantity": "2000"},
            {"price": "1.48", "quantity": "1500"},
        ],
        "asks": [
            {"price": "1.51", "quantity": "800"},
            {"price": "1.52", "quantity": "1200"},
            {"price": "1.53", "quantity": "900"},
        ],
        "spread": "0.01",
        "message": f"Order book for {pair}"
    })


@tool
def get_order_status(order_id: str) -> str:
    """Get the status of an order.

    Args:
        order_id: The order ID to check

    Returns:
        Order status as JSON string
    """
    # TODO: Implement actual order status checking
    return json.dumps({
        "order_id": order_id,
        "status": "partially_filled",
        "pair": "MOVE/USDC",
        "side": "buy",
        "type": "limit",
        "price": "1.50",
        "quantity": "100",
        "filled": "45",
        "remaining": "55",
        "message": f"Order {order_id} is partially filled"
    })


def get_tools() -> List[Any]:
    """Get the list of tools available to the agent."""
    return [place_limit_order, place_market_order, cancel_order, get_order_book, get_order_status]


def validate_openai_api_key() -> None:
    """Validate that OpenAI API key is set."""
    openai_api_key = os.getenv(ENV_OPENAI_API_KEY)
    if not openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required.\n"
            "Please set it before running the agent."
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


class OrderBookAgent:
    def __init__(self):
        self._agent = self._build_agent()
        self._runner = Runner(
            app_name="orderbookagent",
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def _build_agent(self):
        """Build the agent using the create_agent API."""
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
            return json.dumps({"response": validated_output, "success": True})
        except Exception as e:
            print(f"Error in agent invoke: {e}")
            error_message = format_error_message(e)
            return json.dumps({"response": error_message, "success": False, "error": str(e)})

    async def _invoke_agent(self, query: str, session_id: str) -> Any:
        """Invoke the agent with the given query and session."""
        return await self._agent.ainvoke(
            {MESSAGE_KEY_MESSAGES: [{MESSAGE_KEY_ROLE: MESSAGE_ROLE_USER, MESSAGE_KEY_CONTENT: query}]},
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


class OrderBookAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = OrderBookAgent()

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


def create_orderbook_agent_app(card_url: str) -> A2AStarletteApplication:
    """Create and configure the A2A server application for the orderbook agent.

    Args:
        card_url: The base URL where the agent card will be accessible

    Returns:
        A2AStarletteApplication instance configured for the orderbook agent
    """
    agent_card = AgentCard(
        name="OrderBook Agent",
        description="LangGraph powered agent for trading on ClobX order book",
        url=card_url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[create_agent_skill()],
        supports_authenticated_extended_card=False,
    )
    request_handler = DefaultRequestHandler(
        agent_executor=OrderBookAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
        extended_agent_card=agent_card,
    )
