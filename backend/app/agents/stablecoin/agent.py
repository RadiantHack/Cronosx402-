"""
Stablecoin Agent - Ethena Stablecoin Protocol Agent

Tools: mint_stable, redeem_stable, check_peg, get_collateral_ratio
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
MESSAGE_ROLE_USER = "user"
MESSAGE_KEY_MESSAGES = "messages"
MESSAGE_KEY_CONTENT = "content"
MESSAGE_KEY_ROLE = "role"
MESSAGE_KEY_TYPE = "type"
MESSAGE_TYPE_AI = "ai"


def get_system_prompt() -> str:
    return """You are a stablecoin assistant for Ethena on Cronos.

Help users:
- Mint synthetic stablecoins
- Redeem stablecoins for collateral
- Check peg stability
- Monitor collateral ratios

Explain stablecoin mechanisms and risks."""


def create_agent_skill() -> AgentSkill:
    return AgentSkill(
        id="stablecoin_agent",
        name="Stablecoin Agent",
        description="Stablecoin operations on Ethena",
        tags=["stablecoin", "ethena", "defi", "usde"],
        examples=["mint 1000 USDe", "redeem 500 USDe", "check peg status"],
    )


@tool
def mint_stable(amount: str, collateral_asset: str = "USDC") -> str:
    """Mint stablecoins."""
    return json.dumps({
        "status": "success",
        "amount": amount,
        "collateral": collateral_asset,
        "minted": f"{amount} USDe",
        "message": f"Minted {amount} USDe"
    })


@tool
def redeem_stable(amount: str) -> str:
    """Redeem stablecoins."""
    return json.dumps({
        "status": "success",
        "amount": amount,
        "received": f"{amount} USDC",
        "message": f"Redeemed {amount} USDe"
    })


@tool
def check_peg() -> str:
    """Check stablecoin peg status."""
    return json.dumps({
        "current_price": "1.001 USD",
        "peg_deviation": "0.1%",
        "status": "stable",
        "message": "Peg status check"
    })


@tool
def get_collateral_ratio() -> str:
    """Get protocol collateral ratio."""
    return json.dumps({
        "collateral_ratio": "150%",
        "total_collateral": "150M USD",
        "total_supply": "100M USDe",
        "status": "healthy",
        "message": "Collateral ratio check"
    })


def get_tools() -> List[Any]:
    return [mint_stable, redeem_stable, check_peg, get_collateral_ratio]


class StablecoinAgent:
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


class StablecoinAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = StablecoinAgent()

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


def create_stablecoin_agent_app(card_url: str) -> A2AStarletteApplication:
    return A2AStarletteApplication(
        agent_card=AgentCard(
            name="Stablecoin Agent",
            description="Stablecoin operations on Ethena",
            url=card_url,
            version="1.0.0",
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[create_agent_skill()],
            supports_authenticated_extended_card=False,
        ),
        http_handler=DefaultRequestHandler(
            agent_executor=StablecoinAgentExecutor(),
            task_store=InMemoryTaskStore()
        ),
        extended_agent_card=AgentCard(
            name="Stablecoin Agent",
            description="Stablecoin operations on Ethena",
            url=card_url,
            version="1.0.0",
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[create_agent_skill()],
            supports_authenticated_extended_card=False,
        ),
    )
