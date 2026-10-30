"""Lazy OpenAI-compatible client + chat model, routed through Requesty."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import OpenAIChatCompletionsModel, set_tracing_disabled

load_dotenv()
set_tracing_disabled(True)

BASE_URL = os.getenv("BASE_URL", "https://router.requesty.ai/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-5.6-luna")

_chat_model: OpenAIChatCompletionsModel | None = None


def credentials_present() -> bool:
    return bool(os.getenv("REQUESTY_API_KEY"))


def get_chat_completions_model() -> OpenAIChatCompletionsModel:
    """Build the model lazily so this module imports cleanly without credentials."""
    global _chat_model
    if _chat_model is None:
        api_key = os.getenv("REQUESTY_API_KEY")
        if not api_key:
            raise RuntimeError("REQUESTY_API_KEY is not set (copy /root/openai-creds.txt to the project .env)")
        client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
        _chat_model = OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client)
    return _chat_model
