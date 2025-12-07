"""
Liquidity Agent - Meridian & Coral Finance Liquidity Management Agent

Tools: add_liquidity, remove_liquidity, get_pool_info, calculate_impermanent_loss
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
EMPTY_RESPONSE_MESSAGE = "I apologize, but I couldn't generate a response."
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_OPENAI_MODEL = "OPENAI_MODEL"
MESSAGE_TYPE_AI = "ai"
MESSAGE_ROLE_ASSISTANT = "assistant"
MESSAGE_ROLE_USER = "user"
MESSAGE_KEY_MESSAGES = "messages"
MESSAGE_KEY_CONTENT = "content"
MESSAGE_KEY_ROLE = "role"
MESSAGE_KEY_TYPE = "type"
ERROR_API_KEY = "api key"
ERROR_AUTH_MESSAGE = "Authentication error: Please check your OpenAI API key."
ERROR_GENERIC_PREFIX = "Error: "


def get_system_prompt() -> str:
    return """You are a DeFi liquidity management assistant for Meridian and Coral Finance on Cronos.

Help users:
- Add liquidity to pools
- Remove liquidity from pools
- Check pool information (APY, TVL, fees)
- Calculate impermanent loss

Always explain risks and potential returns."""


def create_agent_skill() -> AgentSkill:
    return AgentSkill(
        id="liquidity_agent",
        name="Liquidity Agent",
        description="Liquidity management for Meridian and Coral Finance",
        tags=["liquidity", "defi", "meridian", "coral", "pools"],
        examples=["add liquidity to MOVE/USDC pool", "remove liquidity from pool #123", "show pool info for MOVE/USDC"],
    )


@tool
def add_liquidity(pool: str, token_a_amount: str, token_b_amount: str) -> str:
    """Add liquidity to a pool."""
    return json.dumps({
        "status": "success",
        "pool": pool,
        "token_a_amount": token_a_amount,
        "token_b_amount": token_b_amount,
        "lp_tokens": "1050.5",
        "message": f"Added liquidity to {pool}"
    })


@tool
def remove_liquidity(pool: str, lp_tokens: str) -> str:
    """Remove liquidity from a pool."""
    return json.dumps({
        "status": "success",
        "pool": pool,
        "lp_tokens": lp_tokens,
        "token_a_received": "500 MOVE",
        "token_b_received": "750 USDC",
        "message": f"Removed liquidity from {pool}"
    })


@tool
def get_pool_info(pool: str) -> str:
    """Get pool information."""
    return json.dumps({
        "pool": pool,
        "tvl": "5000000 USD",
        "apy": "45.5%",
        "volume_24h": "250000 USD",
        "fees_24h": "750 USD",
        "message": f"Pool info for {pool}"
    })


@tool
def calculate_impermanent_loss(pool: str, initial_price: str, current_price: str) -> str:
    """Calculate impermanent loss."""
    return json.dumps({
        "pool": pool,
        "initial_price": initial_price,
        "current_price": current_price,
        "impermanent_loss": "2.5%",
        "message": "Impermanent loss calculation"
    })


def get_tools() -> List[Any]:
    return [add_liquidity, remove_liquidity, get_pool_info, calculate_impermanent_loss]


def validate_openai_api_key() -> None:
    if not os.getenv(ENV_OPENAI_API_KEY):
        raise ValueError("OPENAI_API_KEY required")


def create_chat_model() -> ChatOpenAI:
    return ChatOpenAI(model=os.getenv(ENV_OPENAI_MODEL, DEFAULT_MODEL), temperature=DEFAULT_TEMPERATURE)


def is_assistant_message(msg: Any) -> bool:
    if hasattr(msg, MESSAGE_KEY_TYPE):
        return msg.type == MESSAGE_TYPE_AI
    if isinstance(msg, dict):
        return msg.get(MESSAGE_KEY_TYPE) == MESSAGE_TYPE_AI
    return False


def extract_message_content(msg: Any) -> str:
    if hasattr(msg, MESSAGE_KEY_CONTENT):
        return msg.content
    if isinstance(msg, dict):
        return msg.get(MESSAGE_KEY_CONTENT, "")
    return ""


def extract_assistant_response(result: Any) -> str:
    if isinstance(result, dict) and MESSAGE_KEY_MESSAGES in result:
        for msg in reversed(result[MESSAGE_KEY_MESSAGES]):
            if is_assistant_message(msg):
                content = extract_message_content(msg)
                if content:
                    return content
    return ""


class LiquidityAgent:
    def __init__(self):
        self._agent = self._build_agent()

    def _build_agent(self):
        validate_openai_api_key()
        return create_agent(model=create_chat_model(), tools=get_tools(), system_prompt=get_system_prompt())

    async def invoke(self, query: str, session_id: str) -> str:
        try:
            result = await self._agent.ainvoke(
                {MESSAGE_KEY_MESSAGES: [{MESSAGE_KEY_ROLE: MESSAGE_ROLE_USER, MESSAGE_KEY_CONTENT: query}]},
                config={"configurable": {"thread_id": session_id}}
            )
            output = extract_assistant_response(result) or EMPTY_RESPONSE_MESSAGE
            return json.dumps({"response": output, "success": True})
        except Exception as e:
            return json.dumps({"response": f"{ERROR_GENERIC_PREFIX}{e}", "success": False})


class LiquidityAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = LiquidityAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        session_id = getattr(context, "context_id", DEFAULT_SESSION_ID)
        final_content = await self.agent.invoke(query, session_id)
        message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=[Part(root=TextPart(kind="text", text=final_content))]
        )
        await event_queue.enqueue_event(message)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")


def create_liquidity_agent_app(card_url: str) -> A2AStarletteApplication:
    agent_card = AgentCard(
        name="Liquidity Agent",
        description="Liquidity management for Meridian and Coral Finance",
        url=card_url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[create_agent_skill()],
        supports_authenticated_extended_card=False,
    )
    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=DefaultRequestHandler(
            agent_executor=LiquidityAgentExecutor(),
            task_store=InMemoryTaskStore()
        ),
        extended_agent_card=agent_card,
    )
