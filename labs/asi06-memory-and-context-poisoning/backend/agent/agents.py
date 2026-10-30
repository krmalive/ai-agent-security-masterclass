"""Shared LLM client and the policy assistant (interpret + one JSON planner)."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List

from agents import Agent, Runner
from openai import AsyncOpenAI

from backend.config import Config

from .tools import PolicyAssistantTools

_INTERPRET = """You are a policy assistant. Interpret the user's request.
Respond with JSON only: {"intent": "remember|query_memory|get_policy|process_refund|query_order|other", "summary": "brief summary"}"""

_PLAN = """You are a policy assistant. Plan tool calls based on the user's request.
Available tools: add_to_memory(content, category), query_memory(query), get_refund_policy(), query_order(order_id), process_refund(order_id, amount, reason, policy_context)

Rules:
- For "remember X": plan add_to_memory(content=X, category=fact|policy|preference)
- For refund approval: first get_refund_policy(), then process_refund
- For order lookup: use query_order
- Respond with JSON array only: [{"tool": "name", "args": {...}}, ...]
"""


class LLMClient:
    """Requesty-compatible OpenAI Agents SDK wrapper."""

    _configured = False
    _client = None

    def __init__(self) -> None:
        self.model = Config.LLM_MODEL
        if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == "your_api_key_here":
            raise ValueError("OPENAI_API_KEY must be set.")
        if not LLMClient._configured:
            from agents import (
                set_default_openai_api,
                set_default_openai_client,
                set_tracing_disabled,
            )

            LLMClient._client = AsyncOpenAI(
                api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_API_BASE
            )
            set_default_openai_client(LLMClient._client, use_for_tracing=False)
            set_default_openai_api("chat_completions")
            set_tracing_disabled(True)
            LLMClient._configured = True

    def build_model(self):
        from agents import OpenAIChatCompletionsModel

        return OpenAIChatCompletionsModel(
            model=self.model, openai_client=LLMClient._client
        )

    def run_agent_sync(self, agent: Agent, user_input: str) -> str:
        result = asyncio.run(Runner.run(agent, user_input))
        out = result.final_output
        return out if isinstance(out, str) else str(out)

    def run_messages_as_agent(
        self, messages: List[Dict[str, str]], *, agent_name: str
    ) -> str:
        system = "\n\n".join(
            m.get("content", "") for m in messages if m.get("role") == "system"
        )
        user = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in messages
            if m.get("role") != "system"
        )
        agent = Agent(
            name=agent_name,
            instructions=system or "You are a helpful assistant.",
            model=self.build_model(),
        )
        return self.run_agent_sync(agent, user)

    def call_structured(self, messages: List[Dict[str, str]]) -> Any:
        raw = self.run_messages_as_agent(messages, agent_name="ASI06Structured")
        return self.extract_json(raw)

    @staticmethod
    def extract_json(text: str) -> Any:
        text = text.strip()
        fence = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        for start_char, end_char in [("[", "]"), ("{", "}")]:
            start = text.find(start_char)
            if start == -1:
                continue
            depth = 0
            for i in range(start, len(text)):
                if text[i] == start_char:
                    depth += 1
                elif text[i] == end_char:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            break
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON", "raw": text[:500]}


class PolicyAssistant:
    """Interpret the request and plan tools with a single JSON planner."""

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.tools = PolicyAssistantTools()
        self._interpret = Agent(
            name="ASI06IntentInterpreter",
            instructions=_INTERPRET,
            model=self.llm.build_model(),
        )
        self._plan = Agent(
            name="ASI06JsonToolPlanner",
            instructions=_PLAN,
            model=self.llm.build_model(),
        )

    def interpret_request(self, user_message: str) -> Dict[str, Any]:
        try:
            raw = self.llm.run_agent_sync(self._interpret, user_message)
            response = self.llm.extract_json(raw)
            if isinstance(response, dict) and "intent" in response:
                return response
            return {"intent": "other", "summary": str(response)}
        except Exception:
            return {"intent": "other", "summary": user_message}

    def plan_tools(
        self, user_message: str, intent: Dict[str, Any], memory_context: str = ""
    ) -> List[Dict[str, Any]]:
        parts = [
            f"User: {user_message}",
            f"Intent: {json.dumps(intent)}",
            "Plan tool calls as JSON array.",
        ]
        if memory_context:
            parts.insert(2, f"Current memory/policy context:\n{memory_context}")
        try:
            raw = self.llm.run_agent_sync(self._plan, "\n\n".join(parts))
            response = self.llm.extract_json(raw)
            if isinstance(response, list):
                return response
            if isinstance(response, dict) and "plan" in response:
                return response["plan"]
            if isinstance(response, dict) and "tools" in response:
                return response["tools"]
            return []
        except Exception:
            return []

    def get_memory_context(self) -> str:
        policy = self.tools.peek_refund_policy()
        entries = self.tools.memory_store.get_all_memory_entries()
        parts = [f"Refund policy: {policy}"]
        for entry in entries[-5:]:
            parts.append(
                f"Memory: [{entry.get('category')}] {entry.get('content', '')[:100]}"
            )
        return "\n".join(parts)
