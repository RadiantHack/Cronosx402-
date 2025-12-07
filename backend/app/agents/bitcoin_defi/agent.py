"""
Bitcoin DeFi Agent - Avalon Labs Bitcoin DeFi Agent

Tools: wrap_btc, unwrap_btc, get_btc_products, stake_btc
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
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

DEFAULT_MODEL = "gpt-4o-mini"
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
MESSAGE_ROLE_USER = "user"
MESSAGE_KEY_MESSAGES = "messages"
MESSAGE_KEY_CONTENT = "content"
MESSAGE_KEY_ROLE = "role"
MESSAGE_KEY_TYPE = "type"
MESSAGE_TYPE_AI = "ai"


def get_system_prompt() -> str:
    return """You are a Bitcoin DeFi assistant for Avalon Labs on Cronos.

Help users:
- Wrap/unwrap BTC for use in DeFi
- Discover Bitcoin DeFi products
- Stake BTC for yields

Explain Bitcoin bridging and DeFi opportunities."""


def create_agent_skill() -> AgentSkill:
    return AgentSkill(
        id="bitcoin_defi_agent",
        name="Bitcoin DeFi Agent",
        description="Bitcoin DeFi operations on Avalon Labs",
        tags=["bitcoin", "btc", "defi", "avalon", "wrapping"],
        examples=["wrap 0.5 BTC", "show BTC products", "stake BTC"],
    )


@tool
def wrap_btc(amount: str) -> str:
    """Wrap BTC for DeFi use."""
    return json.dumps({
        "status": "success",
        "amount": amount,
        "wrapped_token": "wBTC",
        "message": f"Wrapped {amount} BTC"
    })


@tool
def unwrap_btc(amount: str) -> str:
    """Unwrap BTC."""
    return json.dumps({
        "status": "success",
        "amount": amount,
        "message": f"Unwrapped {amount} wBTC to BTC"
    })


@tool
def get_btc_products() -> str:
    """Get available Bitcoin DeFi products."""
    return json.dumps({
        "products": [
            {"name": "BTC Lending", "apy": "8.5%"},
            {"name": "BTC Staking", "apy": "6.2%"},
            {"name": "BTC Liquidity Pool", "apy": "12.3%"}
        ],
        "message": "Available Bitcoin DeFi products"
    })


@tool
def stake_btc(amount: str) -> str:
    """Stake BTC for yields."""
    return json.dumps({
        "status": "success",
        "amount": amount,
        "apy": "6.2%",
        "message": f"Staked {amount} BTC"
    })


def get_tools() -> List[Any]:
    return [wrap_btc, unwrap_btc, get_btc_products, stake_btc]


class BitcoinDefiAgent:
    def __init__(self):
        self._agent = create_agent(
            model=ChatOpenAI(model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL), temperature=0),
            tools=get_tools(),
            system_prompt=get_system_prompt()
        )

    async def invoke(self, query: str, session_id: str) -> str:
        try:
            result = await self._agent.ainvoke(
                {MESSAGE_KEY_MESSAGES: [{MESSAGE_KEY_ROLE: MESSAGE_ROLE_USER, MESSAGE_KEY_CONTENT: query}]},
                config={"configurable": {"thread_id": session_id}}
            )
            output = ""
            if isinstance(result, dict) and MESSAGE_KEY_MESSAGES in result:
                for msg in reversed(result[MESSAGE_KEY_MESSAGES]):
                    if isinstance(msg, dict) and msg.get(MESSAGE_KEY_TYPE) == MESSAGE_TYPE_AI:
                        output = msg.get(MESSAGE_KEY_CONTENT, "")
                        break
            return json.dumps({"response": output or "No response", "success": True})
        except Exception as e:
            return json.dumps({"response": f"Error: {e}", "success": False})


class BitcoinDefiAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = BitcoinDefiAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        final_content = await self.agent.invoke(query, getattr(context, "context_id", "default"))
        await event_queue.enqueue_event(Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=[Part(root=TextPart(kind="text", text=final_content))]
        ))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")


def create_bitcoin_defi_agent_app(card_url: str) -> A2AStarletteApplication:
    return A2AStarletteApplication(
        agent_card=AgentCard(
            name="Bitcoin DeFi Agent",
            description="Bitcoin DeFi operations on Avalon Labs",
            url=card_url,
            version="1.0.0",
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[create_agent_skill()],
            supports_authenticated_extended_card=False,
        ),
        http_handler=DefaultRequestHandler(
            agent_executor=BitcoinDefiAgentExecutor(),
            task_store=InMemoryTaskStore()
        ),
        extended_agent_card=AgentCard(
            name="Bitcoin DeFi Agent",
            description="Bitcoin DeFi operations on Avalon Labs",
            url=card_url,
            version="1.0.0",
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[create_agent_skill()],
            supports_authenticated_extended_card=False,
        ),
    )
