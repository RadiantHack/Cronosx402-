"""
Lending Agent - MovePosition & Echelon Lending Protocol Agent

Tools: supply_collateral, borrow_asset, repay_loan, check_health_factor
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
MESSAGE_ROLE_USER = "user"
MESSAGE_KEY_MESSAGES = "messages"
MESSAGE_KEY_CONTENT = "content"
MESSAGE_KEY_ROLE = "role"
MESSAGE_KEY_TYPE = "type"


def get_system_prompt() -> str:
    return """You are a lending protocol assistant for MovePosition and Echelon on Cronos.

Help users:
- Supply collateral to lending protocols
- Borrow assets against collateral
- Repay loans
- Monitor health factors and liquidation risks

Always warn about liquidation risks and explain health factors."""


def create_agent_skill() -> AgentSkill:
    return AgentSkill(
        id="lending_agent",
        name="Lending Agent",
        description="Lending and borrowing on MovePosition and Echelon",
        tags=["lending", "borrowing", "defi", "moveposition", "echelon"],
        examples=["supply 1000 USDC as collateral", "borrow 500 USDC", "check my health factor"],
    )


@tool
def supply_collateral(asset: str, amount: str, protocol: str = "moveposition") -> str:
    """Supply collateral to lending protocol."""
    return json.dumps({
        "status": "success",
        "protocol": protocol,
        "asset": asset,
        "amount": amount,
        "collateral_value": "1000 USD",
        "borrowing_power": "750 USD",
        "message": f"Supplied {amount} {asset} as collateral"
    })


@tool
def borrow_asset(asset: str, amount: str, protocol: str = "moveposition") -> str:
    """Borrow asset from lending protocol."""
    return json.dumps({
        "status": "success",
        "protocol": protocol,
        "asset": asset,
        "amount": amount,
        "interest_rate": "5.5%",
        "health_factor": "1.8",
        "message": f"Borrowed {amount} {asset}"
    })


@tool
def repay_loan(asset: str, amount: str, protocol: str = "moveposition") -> str:
    """Repay loan to lending protocol."""
    return json.dumps({
        "status": "success",
        "protocol": protocol,
        "asset": asset,
        "amount": amount,
        "remaining_debt": "200 USDC",
        "health_factor": "2.5",
        "message": f"Repaid {amount} {asset}"
    })


@tool
def check_health_factor(protocol: str = "moveposition") -> str:
    """Check account health factor."""
    return json.dumps({
        "protocol": protocol,
        "health_factor": "1.8",
        "collateral_value": "1000 USD",
        "borrowed_value": "500 USD",
        "liquidation_threshold": "1.2",
        "status": "healthy",
        "message": "Health factor check"
    })


def get_tools() -> List[Any]:
    return [supply_collateral, borrow_asset, repay_loan, check_health_factor]


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


class LendingAgent:
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


class LendingAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = LendingAgent()

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


def create_lending_agent_app(card_url: str) -> A2AStarletteApplication:
    agent_card = AgentCard(
        name="Lending Agent",
        description="Lending and borrowing on MovePosition and Echelon",
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
            agent_executor=LendingAgentExecutor(),
            task_store=InMemoryTaskStore()
        ),
        extended_agent_card=agent_card,
    )
