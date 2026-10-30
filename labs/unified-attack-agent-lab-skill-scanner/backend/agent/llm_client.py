import asyncio
import json
from typing import Any, Dict, List

from openai import AsyncOpenAI
from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)

from backend.config import Config


class LLMClient:
    """
    Mirrors ASI01 wiring pattern:
    - AsyncOpenAI(base_url=Requesty)
    - set_default_openai_client
    - set_default_openai_api("chat_completions")
    - OpenAIChatCompletionsModel(...)
    """

    _configured = False
    _openai_client: AsyncOpenAI | None = None

    def __init__(self) -> None:
        if not LLMClient._configured:
            self._configure()
            LLMClient._configured = True

    def _configure(self) -> None:
        client = AsyncOpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_API_BASE,
        )
        LLMClient._openai_client = client
        set_default_openai_client(client, use_for_tracing=False)
        set_default_openai_api("chat_completions")
        set_tracing_disabled(True)

    def build_model(self) -> OpenAIChatCompletionsModel:
        return OpenAIChatCompletionsModel(
            model=Config.LLM_MODEL,
            openai_client=LLMClient._openai_client,
        )

    def call(self, messages: List[Dict[str, str]]) -> str:
        system_text = "\n\n".join(
            message["content"] for message in messages if message.get("role") == "system"
        ) or "You are a helpful assistant."
        user_text = "\n".join(
            f"{message.get('role', 'user')}: {message.get('content', '')}"
            for message in messages
            if message.get("role") != "system"
        )
        agent = Agent(
            name="UnifiedRuntimeLLM",
            instructions=system_text,
            model=self.build_model(),
        )
        result = asyncio.run(Runner.run(agent, user_text))
        output = result.final_output
        return output if isinstance(output, str) else str(output)

    def call_structured(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        json_hint = {
            "role": "system",
            "content": "Return valid JSON only. Do not include markdown fences.",
        }
        if not messages or messages[0].get("role") != "system":
            messages = [json_hint] + messages
        else:
            messages[0]["content"] += "\n\nReturn valid JSON only. Do not include markdown fences."
        raw = self.call(messages)
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"error": "invalid_json", "raw_response": raw}
