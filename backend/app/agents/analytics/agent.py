"""
Analytics Agent - Flipside Analytics Agent

Tools: get_protocol_tvl, get_trading_volume, get_user_stats, generate_report
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
    return """You are an analytics assistant using Flipside data for Cronos.

Help users:
- Get protocol TVL and metrics
- Analyze trading volumes
- Track user statistics
- Generate custom reports

Provide data-driven insights and trends."""


def create_agent_skill() -> AgentSkill:
    return AgentSkill(
        id="analytics_agent",
        name="Analytics Agent",
        description="Analytics and reporting using Flipside",
        tags=["analytics", "data", "flipside", "metrics", "tvl"],
        examples=["show Cronos TVL", "get trading volume for last 7 days", "generate protocol report"],
    )


@tool
def get_protocol_tvl(protocol: str = "all") -> str:
    """Get Total Value Locked for protocols."""
    return json.dumps({
        "protocol": protocol,
        "tvl": "50M USD",
        "change_24h": "+5.2%",
        "change_7d": "+12.8%",
        "message": f"TVL for {protocol}"
    })


@tool
def get_trading_volume(days: int = 7) -> str:
    """Get trading volume statistics."""
    return json.dumps({
        "period": f"{days} days",
        "total_volume": "25M USD",
        "avg_daily_volume": "3.5M USD",
        "top_pair": "MOVE/USDC",
        "message": f"Trading volume for last {days} days"
    })


@tool
def get_user_stats(address: str = "") -> str:
    """Get user statistics."""
    return json.dumps({
        "address": address or "network_total",
        "total_users": "15000",
        "active_users_24h": "2500",
        "new_users_7d": "1200",
        "message": "User statistics"
    })


@tool
def generate_report(report_type: str = "overview") -> str:
    """Generate analytics report."""
    return json.dumps({
        "report_type": report_type,
        "summary": {
            "tvl": "50M USD",
            "volume_24h": "3.5M USD",
            "users": "15000",
            "transactions": "125000"
        },
        "message": f"Generated {report_type} report"
    })


def get_tools() -> List[Any]:
    return [get_protocol_tvl, get_trading_volume, get_user_stats, generate_report]


class AnalyticsAgent:
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


class AnalyticsAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = AnalyticsAgent()

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


def create_analytics_agent_app(card_url: str) -> A2AStarletteApplication:
    return A2AStarletteApplication(
        agent_card=AgentCard(
            name="Analytics Agent",
            description="Analytics and reporting using Flipside",
            url=card_url,
            version="1.0.0",
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[create_agent_skill()],
            supports_authenticated_extended_card=False,
        ),
        http_handler=DefaultRequestHandler(
            agent_executor=AnalyticsAgentExecutor(),
            task_store=InMemoryTaskStore()
        ),
        extended_agent_card=AgentCard(
            name="Analytics Agent",
            description="Analytics and reporting using Flipside",
            url=card_url,
            version="1.0.0",
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(streaming=True),
            skills=[create_agent_skill()],
            supports_authenticated_extended_card=False,
        ),
    )
