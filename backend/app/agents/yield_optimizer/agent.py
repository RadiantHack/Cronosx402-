"""
Yield Optimizer Agent - Canopy Yield Marketplace Agent

Tools: find_best_yield, deposit_to_vault, withdraw_from_vault, get_apy_history
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


def get_system_prompt() -> str:
    return """You are a yield optimization assistant for Canopy on Cronos.

Help users:
- Find best yield opportunities
- Deposit assets to yield vaults
- Withdraw from vaults
- Track APY history

Always explain risks and auto-compounding strategies."""


def create_agent_skill() -> AgentSkill:
    return AgentSkill(
        id="yield_optimizer_agent",
        name="Yield Optimizer Agent",
        description="Yield optimization for Canopy marketplace",
        tags=["yield", "defi", "canopy", "apy", "vaults"],
        examples=["find best yield for USDC", "deposit 1000 USDC to vault", "show APY history"],
    )


@tool
def find_best_yield(asset: str) -> str:
    """Find best yield opportunities for an asset."""
    return json.dumps({
        "asset": asset,
        "best_vault": "Canopy USDC Vault",
        "apy": "12.5%",
        "tvl": "2000000 USD",
        "risk_level": "low",
        "message": f"Best yield for {asset}"
    })


@tool
def deposit_to_vault(vault: str, amount: str) -> str:
    """Deposit assets to a yield vault."""
    return json.dumps({
        "status": "success",
        "vault": vault,
        "amount": amount,
        "shares": "1005.5",
        "current_apy": "12.5%",
        "message": f"Deposited {amount} to {vault}"
    })


@tool
def withdraw_from_vault(vault: str, shares: str) -> str:
    """Withdraw from a yield vault."""
    return json.dumps({
        "status": "success",
        "vault": vault,
        "shares": shares,
        "amount_received": "1050 USDC",
        "profit": "50 USDC",
        "message": f"Withdrawn from {vault}"
    })


@tool
def get_apy_history(vault: str, days: int = 30) -> str:
    """Get APY history for a vault."""
    return json.dumps({
        "vault": vault,
        "period": f"{days} days",
        "current_apy": "12.5%",
        "avg_apy": "11.8%",
        "max_apy": "15.2%",
        "min_apy": "9.5%",
        "message": f"APY history for {vault}"
    })


def get_tools() -> List[Any]:
    return [find_best_yield, deposit_to_vault, withdraw_from_vault, get_apy_history]


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


class YieldOptimizerAgent:
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
            return json.dumps({"response": f"Error: {e}", "success": False})


class YieldOptimizerAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = YieldOptimizerAgent()

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


def create_yield_optimizer_agent_app(card_url: str) -> A2AStarletteApplication:
    agent_card = AgentCard(
        name="Yield Optimizer Agent",
        description="Yield optimization for Canopy marketplace",
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
            agent_executor=YieldOptimizerAgentExecutor(),
            task_store=InMemoryTaskStore()
        ),
        extended_agent_card=agent_card,
    )
