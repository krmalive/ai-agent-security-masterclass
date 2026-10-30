#!/usr/bin/env python3
"""
Support Assistant Agent using OpenAI Agent SDK
Handles customer queries with inventory and FAQ lookup capabilities.
"""

import os
from dotenv import load_dotenv
from agents import Agent, Runner, set_tracing_disabled
from agents import SQLiteSession
from openai_agent_support_assistant.tools.inventory import lookup_inventory
from openai_agent_support_assistant.tools.faq import lookup_faq
from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI
import asyncio
set_tracing_disabled(True)
load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://router.requesty.ai/v1")

session = SQLiteSession("conversation_123")

_chat_model = None


def _chat_completions_model() -> OpenAIChatCompletionsModel:
    """Build lazily so importing this module does not require credentials."""
    global _chat_model
    if _chat_model is None:
        api_key = os.getenv("REQUESTY_API_KEY")
        if not api_key:
            raise RuntimeError("REQUESTY_API_KEY is not set")
        client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
        _chat_model = OpenAIChatCompletionsModel(
            model="openai/gpt-5.6-luna",
            openai_client=client,
        )
    return _chat_model


def create_support_agent() -> Agent:
    """Create and configure the support assistant agent."""
    agent = Agent(
        name="Support Assistant",
        instructions=(
            "You are a helpful customer support assistant. "
            "Answer user queries about products, orders, shipping, returns, and general questions. "
            "Use lookup_inventory to check product availability and details. "
            "Use lookup_faq to answer common customer questions. "
            "If you can answer directly without tools, do so. "
            "Be friendly, concise, and helpful."
            "Never answer unrelated questions related to anything other than the inventory. This is mandatory."
        ),
        tools=[lookup_inventory, lookup_faq],
        model=_chat_completions_model(),
    )
    return agent


async def main():
    api_key = os.getenv("REQUESTY_API_KEY")
    if not api_key:
        print("Error: REQUESTY_API_KEY not found in environment.")
        return
    
    # Create agent
    agent = create_support_agent()
    
    print("=" * 60)
    print("Support Assistant Agent")
    print("=" * 60)
    print("Ask me about:")
    print("  • Product inventory (e.g., 'Do you have laptops in stock?')")
    print("  • FAQs (e.g., 'What's your return policy?')")
    print("  • General support questions")
    print("\nType 'quit' or 'exit' to end the conversation.")
    print("=" * 60)
    print()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nThank you for contacting support. Have a great day!")
                break
            print("\nAssistant: ", end="", flush=True)
            result = await Runner.run(agent, user_input, session=session)
            print(result.final_output)
            print()
            
        except KeyboardInterrupt:
            print("\n\nThank you for contacting support. Have a great day!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            print("Please try again.\n")


if __name__ == "__main__":
    asyncio.run(main())

