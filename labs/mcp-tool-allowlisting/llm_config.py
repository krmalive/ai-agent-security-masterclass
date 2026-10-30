"""Lazy OpenAI client + chat-completions model for openai-agents 0.17.x."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import OpenAIChatCompletionsModel, set_tracing_disabled

load_dotenv()
set_tracing_disabled(True)

BASE_URL = os.getenv("BASE_URL", "https://router.requesty.ai/v1")

_chat_model: OpenAIChatCompletionsModel | None = None


def get_chat_completions_model() -> OpenAIChatCompletionsModel:
    global _chat_model
    if _chat_model is None:
        api_key = os.getenv("REQUESTY_API_KEY")
        if not api_key:
            raise RuntimeError("REQUESTY_API_KEY is not set")
        client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
        _chat_model = OpenAIChatCompletionsModel(
            model="openai/gpt-4.1",
            openai_client=client,
        )
    return _chat_model
