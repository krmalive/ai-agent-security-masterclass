#!/usr/bin/env python3
"""
MCP SSE Transport Example

Simple weather client using MCP SSE transport.
"""

import asyncio
import os
import sys

from agents import Agent, Runner
from agents.mcp import MCPServerSse
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel,set_tracing_disabled
from dotenv import load_dotenv

set_tracing_disabled(True)

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://router.requesty.ai/v1")

_chat_model = None


def get_model() -> OpenAIChatCompletionsModel:
    """Lazily build the chat model after REQUESTY_API_KEY is verified in main()."""
    global _chat_model
    if _chat_model is None:
        api_key = os.getenv("REQUESTY_API_KEY")
        if not api_key:
            raise RuntimeError("REQUESTY_API_KEY is not set")
        _chat_model = OpenAIChatCompletionsModel(
            model="openai/gpt-5.6-luna",
            openai_client=AsyncOpenAI(api_key=api_key, base_url=BASE_URL),
        )
    return _chat_model


async def main():
    """Main function."""
    if not os.getenv("REQUESTY_API_KEY"):
        print("Error: REQUESTY_API_KEY not found in environment.")
        sys.exit(1)

    server_url = os.getenv("WEATHER_SERVER_URL", "http://localhost:8443/sse")

    weather_server = MCPServerSse(
        name="WeatherServer",
        params={"url": server_url},
        client_session_timeout_seconds=300
    )

    try:
        async with weather_server:
            print("Connected to weather server")

            agent = Agent(
                name="WeatherAssistant",
                model=get_model(),
                instructions=(
                    "You are a weather assistant. For cities, get coordinates and provide forecasts. "
                    "For states, provide alerts. Handle both intelligently.show your reasoning process in the output."
                ),
                mcp_servers=[weather_server],
            )

            while True:
                place = input("\nEnter US city/state (or 'quit'): ").strip()
                if place.lower() == 'quit':
                    break

                task = f"Provide weather information for {place}.show your reasoning in the output."
                result = await Runner.run(agent, task)

                print("\n" + "=" * 40)
                print(result.final_output)
                print("=" * 40)

    except Exception as e:
        print(f" Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())

