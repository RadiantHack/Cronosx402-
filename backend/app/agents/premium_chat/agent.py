"""
Premium Test Agent - Real Chat with OpenAI LLM

This agent provides a real conversational AI experience using OpenAI's GPT model.
It's designed for testing x402 payments with actual LLM-powered responses.

ARCHITECTURE:
- Uses OpenAI ChatOpenAI for real conversational AI
- Includes tools for crypto-related queries
- Proper session management
- Real API integration

ENVIRONMENT VARIABLES:
- OPENAI_API_KEY: Required - OpenAI API key
"""

import os
import json
from typing import Any, List

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

# Constants
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
MESSAGE_ROLE_USER = "user"
MESSAGE_KEY_MESSAGES = "messages"
MESSAGE_KEY_CONTENT = "content"
MESSAGE_KEY_ROLE = "role"
MESSAGE_KEY_TYPE = "type"
MESSAGE_TYPE_AI = "ai"


def validate_openai_api_key() -> None:
    """Validate that OpenAI API key is set."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.strip() == "":
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please set your OpenAI API key in the .env file."
        )


def create_chat_model() -> ChatOpenAI:
    """Create and configure the ChatOpenAI model."""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        temperature=DEFAULT_TEMPERATURE,
        api_key=os.getenv("OPENAI_API_KEY"),
    )


@tool
def get_crypto_price(symbol: str) -> str:
    """Get the current price of a cryptocurrency symbol (BTC, ETH, CRO, etc.)."""
    try:
        import requests
        response = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            symbol_lower = symbol.lower()
            if symbol_lower in data and "usd" in data[symbol_lower]:
                price = data[symbol_lower]["usd"]
                return json.dumps({"symbol": symbol, "price": price, "currency": "USD"})
        return json.dumps({"error": f"Could not fetch price for {symbol}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_crypto_market_info(symbol: str) -> str:
    """Get market information for a cryptocurrency (market cap, volume, 24h change)."""
    try:
        import requests
        response = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true&include_24hr_change=true",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            symbol_lower = symbol.lower()
            if symbol_lower in data:
                info = data[symbol_lower]
                return json.dumps({
                    "symbol": symbol,
                    "price": info.get("usd"),
                    "market_cap": info.get("usd_market_cap"),
                    "volume_24h": info.get("usd_24h_vol"),
                    "change_24h": info.get("usd_24h_change"),
                })
        return json.dumps({"error": f"Could not fetch market info for {symbol}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_system_prompt() -> str:
    """Get the system prompt for the premium chat agent."""
    return """You are a helpful, friendly AI assistant specialized in cryptocurrency and blockchain technology.

Your strengths:
- Answering questions about cryptocurrencies (Bitcoin, Ethereum, Cronos, etc.)
- Explaining blockchain concepts and DeFi
- Providing market analysis and price information
- Helping with Web3 and crypto-related topics
- Being conversational and engaging

When users ask about crypto prices or market data:
1. Use the available tools to fetch real-time data
2. Present information clearly with context
3. Provide helpful insights based on the data

For general conversations:
- Be friendly and helpful
- Provide accurate information
- Ask clarifying questions if needed
- Offer to help with crypto-related topics

Remember: You're a premium chat service, so provide thoughtful, detailed responses that justify the premium nature of this interaction."""


def get_tools() -> List[Any]:
    """Get the list of tools available to the agent."""
    return [get_crypto_price, get_crypto_market_info]


def extract_assistant_response(result: Any) -> str:
    """Extract the assistant's response from the agent result."""
    if isinstance(result, dict):
        # Check for messages key
        if MESSAGE_KEY_MESSAGES in result:
            messages = result[MESSAGE_KEY_MESSAGES]
            if isinstance(messages, list):
                # Find the last assistant message
                for msg in reversed(messages):
                    if isinstance(msg, dict):
                        if msg.get(MESSAGE_KEY_TYPE) == MESSAGE_TYPE_AI:
                            return msg.get(MESSAGE_KEY_CONTENT, "")
    return ""


class PremiumChatAgent:
    """Premium chat agent powered by OpenAI LLM."""

    def __init__(self):
        """Initialize the premium chat agent."""
        self._agent = self._build_agent()

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

    async def invoke(self, query: str) -> str:
        """Invoke the agent with a query and return JSON response."""
        try:
            result = await self._agent.ainvoke(
                {MESSAGE_KEY_MESSAGES: [{MESSAGE_KEY_ROLE: MESSAGE_ROLE_USER, MESSAGE_KEY_CONTENT: query}]},
                config={"configurable": {"thread_id": "premium_chat"}},
            )
            print(f"[DEBUG] Agent result type: {type(result)}")
            print(f"[DEBUG] Agent result: {result}")
            output = extract_assistant_response(result)
            print(f"[DEBUG] Extracted output: {output}")
            if not output:
                # Fallback to default message
                output = "I'm here to help with crypto and blockchain questions. What would you like to know?"
            return json.dumps({"response": output, "success": True})
        except Exception as e:
            error_msg = str(e)
            print(f"[DEBUG] Exception: {error_msg}")
            if "OPENAI_API_KEY" in error_msg or "api key" in error_msg.lower():
                error_msg = "OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."
            return json.dumps({"response": f"Error: {error_msg}", "success": False, "error": error_msg})


def create_simple_test_agent() -> FastAPI:
    """Create the premium chat agent FastAPI app."""
    app = FastAPI(title="Premium Chat Agent")
    agent = PremiumChatAgent()

    @app.get("/.well-known/agent.json")
    async def agent_card():
        """Agent card endpoint for discovery."""
        return {
            "name": "Premium Chat Agent",
            "description": "AI-powered premium chat for cryptocurrency and blockchain discussions",
            "version": "1.0.0",
            "capabilities": {
                "streaming": False,
                "tool_use": True,
            },
            "skills": [
                {
                    "id": "crypto_chat",
                    "name": "Premium Crypto Chat",
                    "description": "Real-time conversational AI for cryptocurrency and blockchain topics",
                    "tags": ["chat", "premium", "crypto", "x402"],
                }
            ],
        }

    @app.post("/")
    async def handle_message(request: Request):
        """Handle incoming chat messages with real LLM responses."""
        try:
            body = await request.json()
            user_message = body.get("message", "")
            
            if not user_message or not user_message.strip():
                return JSONResponse(
                    status_code=400,
                    content={"error": "Message cannot be empty"},
                )
            
            # Use the agent to generate a real response
            response_json = await agent.invoke(user_message)
            response_data = json.loads(response_json)

            return {
                "response": response_data.get("response", ""),
                "status": "success" if response_data.get("success") else "error",
                "paid": True,
            }
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid JSON in request body"},
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Internal server error: {str(e)}"},
            )

    return app
