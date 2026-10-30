import os

from dotenv import load_dotenv

load_dotenv()

from agents import Agent, Runner
from agents.mcp import MCPServerStdio

from llm_config import get_chat_completions_model


def _filesystem_mcp() -> MCPServerStdio:
    home = os.getenv("HOME")
    if not home:
        raise RuntimeError("HOME is not set (required for insecure demo root)")
    return MCPServerStdio(
        name="filesystem",
        params={
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                os.getcwd(),
                home,
            ],
        },
        cache_tools_list=True,
        client_session_timeout_seconds=300,
    )


async def perform_file_ops(user_prompt: str) -> str:
    file_mcp = _filesystem_mcp()
    async with file_mcp as fss:
        agent = Agent(
            name="fs_agent",
            model=get_chat_completions_model(),
            instructions="""
            You are a helpful assistant tasked with helping the user read file contents
            on the server and perform other file operations.
            """,
            mcp_servers=[fss],
        )
        runner = await Runner.run(agent, user_prompt, max_turns=10)
        return runner.final_output
