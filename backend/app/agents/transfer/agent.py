"""
Transfer Agent - Cronos Native CRO Transfer Agent

This agent helps users transfer native CRO tokens on Cronos blockchain.
It extracts transfer parameters from user queries and returns structured
responses that trigger frontend actions for transaction execution.
"""

import os
import uuid
import json
import pathlib
from typing import Any, List, Dict, Optional

import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file
backend_dir = pathlib.Path(__file__).parent.parent.parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
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
DEFAULT_PORT = 9011
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
    return """You are a helpful Web3 assistant specializing in transferring native CRO tokens on Cronos blockchain.

When users ask to transfer tokens:
1. Extract the token type:
   - If user says "transfer token" or "send token" without specifying which token, you MUST ask: "Which token would you like to transfer? (e.g., CRO, USDC, USDT, etc.)"
   - If user says "transfer CRO", "send CRO", "transfer 1 CRO", etc., the token is CRO
   - If user says "transfer USDC", "send USDT", etc., note that currently only native CRO transfers are supported
   - If user says "1 token" or just "1" without specifying token, assume they mean CRO (native token)
   - CRITICAL: If the user says "transfer token" without specifying which token, you MUST ask them which token they want to transfer before proceeding
2. Extract the transfer amount:
   - Look for numbers followed by "CRO", "TCRO", or "token"
   - Examples: "1 CRO", "0.5 CRO", "10 TCRO", "1 token", "transfer 1 to 0x..."
   - If user says "1 token" or just "1" without specifying token, assume they mean CRO
   - If no amount is specified, ask the user for the amount
2. Extract the recipient address:
   - Look for Ethereum/Cronos addresses (0x... format, 42 characters)
   - Validate that the address starts with "0x" and is 42 characters long
   - If no address is provided, ask the user for the recipient address
3. Determine the network:
   - CRITICAL: Always ask the user to confirm which network they want to use (mainnet or testnet) before proceeding
   - If user explicitly mentions "testnet", "TCRO", "test", or "on testnet", use "testnet"
   - If user explicitly says "CRO on testnet" or "CRO on mainnet", use the specified network
   - If the user does not explicitly specify the network, you MUST ask them: "Which network would you like to use - mainnet or testnet?"
   - Do NOT default to mainnet without user confirmation - always ask first
4. Return a structured response with transfer parameters in JSON format:
   {
     "action": "initiate_transfer",
     "amount": "1.0",
     "recipient": "0x...",
     "network": "mainnet" or "testnet",
     "token": "CRO" or "TCRO",
     "success": true
   }

5. After the transfer is executed by the frontend:
   - The frontend will return a result with "transactionHash" field
   - You MUST include the transaction hash in your response to the user
   - Format: "Transfer completed successfully. Transaction hash: 0x..."
   - Always provide the full transaction hash so users can track it on block explorers
   - If the transfer fails, clearly explain the error to the user

Special handling:

- When user says "transfer token" or "send token" without specifying which token, you MUST ask: "Which token would you like to transfer? (e.g., CRO, USDC, USDT, etc.)"
- When user says "CRO on testnet" or "on testnet", set network to "testnet"
- Always validate addresses are in 0x format and 42 characters long
- Amounts should be in CRO (not wei)
- CRITICAL: Always ask the user to confirm the network (mainnet or testnet) before proceeding with the transfer
- Do NOT default to mainnet - always get explicit confirmation from the user
- Only support native CRO transfers (not ERC-20 tokens) - if user requests ERC-20 token transfer, inform them that only native CRO transfers are currently supported
- Return JSON format that can be easily parsed by the orchestrator

Address validation:
- Addresses should start with 0x and contain valid hexadecimal characters
- If there's an error, return JSON with "success": false and "error" field explaining the issue"""


def get_port() -> int:
    """Get the port number from environment or default."""
    return int(os.getenv(ENV_ITINERARY_PORT, str(DEFAULT_PORT)))


def get_card_url(port: int) -> str:
    """Get the card URL from environment or construct from port."""
    return os.getenv(ENV_RENDER_EXTERNAL_URL, f"http://localhost:{port}")


def create_agent_skill() -> AgentSkill:
    """Create the agent skill definition."""
    return AgentSkill(
        id="transfer_agent",
        name="Transfer Agent",
        description="Transfer Agent for sending native CRO tokens on Cronos",
        tags=["transfer", "cronos", "web3", "crypto", "cro"],
        examples=[
            "transfer 1 CRO to 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "send 0.5 CRO to 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "transfer 10 TCRO to 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb on testnet",
            "send 2 CRO to 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb on mainnet",
        ],
    )


def create_agent_card(port: int) -> AgentCard:
    """Create the public agent card."""
    card_url = get_card_url(port)
    skill = create_agent_skill()
    return AgentCard(
        name="Transfer Agent",
        description=(
            "LangGraph powered agent that helps to transfer "
            "native CRO tokens on Cronos blockchain"
        ),
        url=card_url,
        version="1.0.0",
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
    if len(address) != 42:
        return False
    hex_part = address[2:]
    if not all(c in "0123456789abcdefABCDEF" for c in hex_part):
        return False
    return True


def extract_transfer_params(query: str) -> Dict[str, Any]:
    """Extract transfer parameters from user query.
    
    Args:
        query: User query string
        
    Returns:
        Dictionary with transfer parameters or error
    """
    query_lower = query.lower()
    
    # Extract amount
    amount = None
    amount_str = None
    
    # Look for patterns like "1 CRO", "0.5 CRO", "10 TCRO"
    import re
    amount_patterns = [
        r'(\d+\.?\d*)\s*(?:cro|tcro)',
        r'(?:cro|tcro)\s*(\d+\.?\d*)',
        r'(\d+\.?\d*)',
    ]
    
    for pattern in amount_patterns:
        match = re.search(pattern, query_lower)
        if match:
            try:
                amount = float(match.group(1))
                amount_str = match.group(1)
                break
            except (ValueError, IndexError):
                continue
    
    # Extract recipient address (0x followed by 40 hex chars)
    recipient = None
    address_pattern = r'0x[a-fA-F0-9]{40}'
    address_match = re.search(address_pattern, query)
    if address_match:
        recipient = address_match.group(0)
        if not validate_address(recipient):
            recipient = None
    
    # Determine network
    network = "mainnet"
    if "testnet" in query_lower or "tcro" in query_lower:
        network = "testnet"
    
    # Determine token
    token = "CRO"
    if network == "testnet":
        token = "TCRO"
    
    return {
        "amount": amount_str if amount_str else None,
        "recipient": recipient,
        "network": network,
        "token": token,
        "has_amount": amount is not None,
        "has_recipient": recipient is not None,
    }


@tool
def initiate_transfer(amount: str, recipient: str, network: str = "mainnet") -> str:
    """Initiate a transfer of native CRO tokens on Cronos.

    Args:
        amount: The amount of CRO to transfer (as a string, e.g., "1.0")
        recipient: The recipient wallet address (0x... format, 42 characters)
        network: The network to use - "mainnet" or "testnet" (default: "mainnet")

    Returns:
        A JSON string with transfer parameters that will trigger a frontend action
    """
    # Validate address
    if not validate_address(recipient):
        return json.dumps({
            "error": f"Invalid recipient address: {recipient}. Address must start with 0x and be 42 characters long.",
            "success": False,
        })
    
    # Validate amount
    try:
        amount_float = float(amount)
        if amount_float <= 0:
            return json.dumps({
                "error": f"Invalid amount: {amount}. Amount must be greater than 0.",
                "success": False,
            })
    except (ValueError, TypeError):
        return json.dumps({
            "error": f"Invalid amount: {amount}. Amount must be a valid number.",
            "success": False,
        })
    
    # Validate network
    network_lower = network.lower()
    if network_lower not in ["mainnet", "testnet"]:
        return json.dumps({
            "error": f"Invalid network: {network}. Must be 'mainnet' or 'testnet'.",
            "success": False,
        })
    
    # Return structured response that will trigger frontend action
    response = {
        "action": "initiate_transfer",
        "amount": str(amount_float),
        "recipient": recipient,
        "network": network_lower,
        "token": "CRO" if network_lower == "mainnet" else "TCRO",
        "success": True,
        "message": f"Ready to transfer {amount_float} {('CRO' if network_lower == 'mainnet' else 'TCRO')} to {recipient} on {network_lower}.",
    }
    
    return json.dumps(response)


def get_tools() -> List[Any]:
    """Get the list of tools available to the agent."""
    return [initiate_transfer]


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


class TransferAgent:
    def __init__(self):
        self._agent = self._build_agent()
        self._runner = Runner(
            app_name="transferagent",
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


class TransferAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = TransferAgent()

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


def create_transfer_agent_app(card_url: str) -> A2AStarletteApplication:
    """Create and configure the A2A server application for the transfer agent.

    Args:
        card_url: The base URL where the agent card will be accessible

    Returns:
        A2AStarletteApplication instance configured for the transfer agent
    """
    agent_card = AgentCard(
        name="Transfer Agent",
        description=(
            "LangGraph powered agent that helps to transfer "
            "native CRO tokens on Cronos blockchain"
        ),
        url=card_url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[create_agent_skill()],
        supports_authenticated_extended_card=False,
    )
    request_handler = DefaultRequestHandler(
        agent_executor=TransferAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
        extended_agent_card=agent_card,
    )


if __name__ == "__main__":
    port = get_port()
    card_url = get_card_url(port)
    app = create_transfer_agent_app(card_url)
    uvicorn.run(app.build(), host="0.0.0.0", port=port)

