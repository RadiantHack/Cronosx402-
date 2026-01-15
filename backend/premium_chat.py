#!/usr/bin/env python3
"""
Test script for the Premium Chat Agent with real LLM responses.
"""

import asyncio
import json
import httpx

async def premium_chat():
    """Test the premium chat endpoint."""
    
    url = "http://localhost:8000/premium_chat/"
    
    # Test messages
    test_messages = [
        "What is Bitcoin?",
        "Tell me about Cronos blockchain",
        "What's the current price of Ethereum?",
        "Explain DeFi to me"
    ]
    
    async with httpx.AsyncClient() as client:
        for message in test_messages:
            print(f"\n{'='*60}")
            print(f"User: {message}")
            print(f"{'='*60}")
            
            try:
                response = await client.post(
                    url,
                    json={"message": message},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    assistant_response = result.get("response", "No response")
                    print(f"Agent: {assistant_response}")
                    print(f"Status: {result.get('status', 'unknown')}")
                elif response.status_code == 402:
                    print("Payment required (402) - Expected without x402 header")
                    print(f"Response: {response.text}")
                else:
                    print(f"Error {response.status_code}: {response.text}")
                    
            except Exception as e:
                print(f"Error: {e}")
    
    print(f"\n{'='*60}")
    print("Test completed!")

if __name__ == "__main__":
    print("Testing Premium Chat Agent...")
    print("Make sure the backend is running on http://localhost:8000")
    asyncio.run(premium_chat())
