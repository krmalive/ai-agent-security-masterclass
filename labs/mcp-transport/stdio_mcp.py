#!/usr/bin/env python3
"""
MCP Stdio Transport Example

Demonstrates how to use the OpenAI Agents SDK with MCP stdio transport
to interact with GitHub repositories.
"""

import asyncio
import os
import sys

from agents import Agent, Runner, OpenAIChatCompletionsModel
from agents import enable_verbose_stdout_logging, set_tracing_disabled
from agents.mcp import MCPServerStdio
from config_manager import ConfigManager
from dotenv import load_dotenv
from openai import AsyncOpenAI

set_tracing_disabled(True)
enable_verbose_stdout_logging()
load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://router.requesty.ai/v1")

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


async def main():
    """Main function to demonstrate MCP stdio transport."""
    if not os.getenv("REQUESTY_API_KEY"):
        print("Error: REQUESTY_API_KEY not found in environment.")
        sys.exit(1)

    # Initialize config manager
    config = ConfigManager()
    
    # Get GitHub PAT securely
    github_pat = config.get_github_pat()
    
    # Initialize MCP server with stdio transport
    server = MCPServerStdio(
        name="GitHubServer",
        params={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": github_pat,
            },
        },
        client_session_timeout_seconds=300
    )
    
    # Create agent with MCP server
    agent = Agent(
        name="GitHubIssueFetcher",
        model=_chat_completions_model(),
        instructions=(
            "You are a helpful assistant that fetches GitHub repository information. "
            "When asked for issues, retrieve and present them in a clear, organized format. "
            "Provide issue numbers, titles, and status information."
        ),
        mcp_servers=[server],

    )
    
    # Run the agent to fetch top 5 issues
    print("\nFetching top 5 issues from openai/openai-agents-python...\n")
    
    async with server:
        result = await Runner.run(
            agent,
            input="Get the latest 5 issues and their description if exists from the repository openai/openai-agents-python. List them with their issue numbers, titles, and current status.",
        )
        
        print("=" * 80)
        print("RESULT:")
        print("=" * 80)
        print(result.final_output)
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

