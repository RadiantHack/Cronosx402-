"""
Prediction Agent - BRKT Prediction Market Agent

This module implements an AI-powered agent for interacting with BRKT,
the on-chain prediction market on Cronos.

Tools: create_market, place_prediction, resolve_market, get_market_odds
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
from a2a.types import AgentCapabilities, AgentCard, AgentSkill, Message, Part, Role, TextPart
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0
DEFAULT_SESSION_ID = "default_session"
EMPTY_RESPONSE_MESSAGE = "I apologize, but I couldn't generate a response. Please try rephrasing your question."

ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_OPENAI_MODEL = "OPENAI_MODEL"

MESSAGE_TYPE_AI = "ai"
MESSAGE_ROLE_ASSISTANT = "assistant"
MESSAGE_ROLE_USER = "user"
MESSAGE_KEY_MESSAGES = "messages"
MESSAGE_KEY_OUTPUT = "output"
MESSAGE_KEY_CONTENT = "content"
MESSAGE_KEY_ROLE = "role"
MESSAGE_KEY_TYPE = "type"

ERROR_API_KEY = "api key"
ERROR_TIMEOUT = "timeout"
ERROR_AUTH_MESSAGE = "Authentication error: Please check your OpenAI API key configuration."
ERROR_TIMEOUT_MESSAGE = "Request timed out. Please try again."
ERROR_GENERIC_PREFIX = "I encountered an error while processing your request: "


def get_system_prompt() -> str:
    return """You are a helpful prediction market assistant specializing in BRKT on Cronos.

When users want to interact with prediction markets:
1. Extract market details (question, outcomes, resolution date)
2. Determine action: create market, place prediction, check odds, resolve market
3. Extract prediction amount and chosen outcome
4. Use appropriate tools to execute operations

Available operations:
- Create new prediction markets
- Place predictions on existing markets
- Check current market odds
- Resolve markets (for market creators)

Always explain odds and potential returns.
Warn about market resolution criteria.
If there's an error, explain it clearly."""


def create_agent_skill() -> AgentSkill:
    return AgentSkill(
        id="prediction_agent",
        name="Prediction Agent",
        description="Prediction market agent for BRKT on Cronos",
        tags=["prediction", "betting", "brkt", "markets"],
        examples=[
            "create market: Will ETH reach $5000 by end of 2024?",
            "bet 100 USDC on YES for market #123",
            "show odds for market #123",
            "resolve market #456",
        ],
    )


@tool
def create_market(question: str, outcomes: str, resolution_date: str, category: str = "crypto") -> str:
    """Create a new prediction market.
    
    Args:
        question: The market question
        outcomes: Comma-separated possible outcomes (e.g., "YES,NO")
        resolution_date: When the market resolves (ISO format)
        category: Market category (default: crypto)
    
    Returns:
        Market creation confirmation as JSON
    """
    # TODO: Implement actual BRKT market creation
    return json.dumps({
        "status": "success",
        "market_id": "MKT-789",
        "question": question,
        "outcomes": outcomes.split(","),
        "resolution_date": resolution_date,
        "category": category,
        "message": f"Market created successfully: {question}"
    })


@tool
def place_prediction(market_id: str, outcome: str, amount: str) -> str:
    """Place a prediction on a market.
    
    Args:
        market_id: The market ID
        outcome: The outcome to bet on
        amount: Amount to bet
    
    Returns:
        Prediction confirmation as JSON
    """
    # TODO: Implement actual prediction placement
    return json.dumps({
        "status": "success",
        "market_id": market_id,
        "outcome": outcome,
        "amount": amount,
        "shares": "105.5",
        "potential_return": "210 USDC",
        "message": f"Placed {amount} on {outcome} for market {market_id}"
    })


@tool
def get_market_odds(market_id: str) -> str:
    """Get current odds for a market.
    
    Args:
        market_id: The market ID
    
    Returns:
        Market odds as JSON
    """
    # TODO: Implement actual odds fetching
    return json.dumps({
        "market_id": market_id,
        "question": "Will ETH reach $5000 by end of 2024?",
        "odds": {
            "YES": "45%",
            "NO": "55%"
        },
        "total_volume": "50000 USDC",
        "resolution_date": "2024-12-31",
        "message": "Current market odds"
    })


@tool
def resolve_market(market_id: str, winning_outcome: str) -> str:
    """Resolve a market (creator only).
    
    Args:
        market_id: The market ID
        winning_outcome: The winning outcome
    
    Returns:
        Resolution confirmation as JSON
    """
    # TODO: Implement actual market resolution
    return json.dumps({
        "status": "success",
        "market_id": market_id,
        "winning_outcome": winning_outcome,
        "total_payout": "75000 USDC",
        "message": f"Market {market_id} resolved with outcome: {winning_outcome}"
    })


def get_tools() -> List[Any]:
    return [create_market, place_prediction, get_market_odds, resolve_market]


def validate_openai_api_key() -> None:
    openai_api_key = os.getenv(ENV_OPENAI_API_KEY)
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required.")


def create_chat_model() -> ChatOpenAI:
    model_name = os.getenv(ENV_OPENAI_MODEL, DEFAULT_MODEL)
    return ChatOpenAI(model=model_name, temperature=DEFAULT_TEMPERATURE)


def is_assistant_message(message: Any) -> bool:
    if hasattr(message, MESSAGE_KEY_TYPE) and hasattr(message, MESSAGE_KEY_CONTENT):
        return message.type == MESSAGE_TYPE_AI or getattr(message, MESSAGE_KEY_ROLE, None) == MESSAGE_ROLE_ASSISTANT
    if isinstance(message, dict):
        return message.get(MESSAGE_KEY_ROLE) == MESSAGE_ROLE_ASSISTANT or message.get(MESSAGE_KEY_TYPE) == MESSAGE_TYPE_AI
    return False


def extract_message_content(message: Any) -> str:
    if hasattr(message, MESSAGE_KEY_CONTENT):
        return message.content
    if isinstance(message, dict):
        return message.get(MESSAGE_KEY_CONTENT, "")
    return ""


def extract_assistant_response(result: Any) -> str:
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
    for message in reversed(messages):
        if is_assistant_message(message):
            content = extract_message_content(message)
            if content:
                return content
    return ""


def _extract_last_message_content(messages: List[Any]) -> str:
    if not messages:
        return ""
    return extract_message_content(messages[-1])


def _extract_fallback_output(result: Any) -> str:
    if isinstance(result, dict):
        return result.get(MESSAGE_KEY_OUTPUT, "")
    return str(result)


def format_error_message(error: Exception) -> str:
    error_msg = str(error).lower()
    if ERROR_API_KEY in error_msg:
        return ERROR_AUTH_MESSAGE
    if ERROR_TIMEOUT in error_msg:
        return ERROR_TIMEOUT_MESSAGE
    return f"{ERROR_GENERIC_PREFIX}{error}. Please try again."


class PredictionAgent:
    def __init__(self):
        self._agent = self._build_agent()
        self._runner = Runner(
            app_name="predictionagent",
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def _build_agent(self):
        validate_openai_api_key()
        model = create_chat_model()
        tools = get_tools()
        system_prompt = get_system_prompt()
        return create_agent(model=model, tools=tools, system_prompt=system_prompt)

    async def invoke(self, query: str, session_id: str) -> str:
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
        return await self._agent.ainvoke(
            {MESSAGE_KEY_MESSAGES: [{MESSAGE_KEY_ROLE: MESSAGE_ROLE_USER, MESSAGE_KEY_CONTENT: query}]},
            config={"configurable": {"thread_id": session_id}},
        )

    def _validate_output(self, output: str) -> str:
        if not output or not output.strip():
            return EMPTY_RESPONSE_MESSAGE
        return output


def get_session_id(context: RequestContext) -> str:
    return getattr(context, "context_id", DEFAULT_SESSION_ID)


def create_message(content: str) -> Message:
    return Message(
        message_id=str(uuid.uuid4()),
        role=Role.agent,
        parts=[Part(root=TextPart(kind="text", text=content))],
    )


class PredictionAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = PredictionAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        session_id = get_session_id(context)
        final_content = await self.agent.invoke(query, session_id)
        message = create_message(final_content)
        await event_queue.enqueue_event(message)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")


def create_prediction_agent_app(card_url: str) -> A2AStarletteApplication:
    agent_card = AgentCard(
        name="Prediction Agent",
        description="LangGraph powered agent for BRKT prediction markets",
        url=card_url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[create_agent_skill()],
        supports_authenticated_extended_card=False,
    )
    request_handler = DefaultRequestHandler(
        agent_executor=PredictionAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
        extended_agent_card=agent_card,
    )
